#!/usr/bin/env python3
"""Train the SMS spam gate used before the action-planning tools."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "external" / "SMSSpamCollection"
MODEL_DIR = ROOT / "artifacts" / "models"
FIG_DIR = ROOT / "artifacts" / "figures"
REPORT_DIR = ROOT / "artifacts" / "reports"

matplotlib.rcParams["font.sans-serif"] = ["Arial Unicode MS", "Songti SC", "STHeiti"]
matplotlib.rcParams["axes.unicode_minus"] = False


def build_nb() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            ("classifier", MultinomialNB(alpha=0.2)),
        ]
    )


def build_logistic() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=2.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )


def build_union_logistic() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=3,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    C=2.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )


def score_predictions(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro")),
        "spam_precision": float(precision_score(y_true, predictions, pos_label=1)),
        "spam_recall": float(recall_score(y_true, predictions, pos_label=1)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
    }


def plot_confusion(y_true: pd.Series, probabilities: np.ndarray, output: Path) -> None:
    predictions = (probabilities >= 0.5).astype(int)
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4.9, 4.2))
    image = ax.imshow(matrix, cmap="Oranges")
    labels = ["正常短信", "垃圾短信"]
    ax.set_xticks([0, 1], labels=labels)
    ax.set_yticks([0, 1], labels=labels)
    ax.set_xlabel("预测")
    ax.set_ylabel("真实")
    ax.set_title("短信垃圾检测混淆矩阵")
    for row in range(2):
        for col in range(2):
            ax.text(
                col,
                row,
                str(matrix[row, col]),
                ha="center",
                va="center",
                color="white" if matrix[row, col] > matrix.max() / 2 else "#172033",
                fontsize=13,
            )
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for directory in [MODEL_DIR, FIG_DIR, REPORT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(
        DATA_PATH,
        sep="\t",
        header=None,
        names=["label", "message"],
        encoding="latin-1",
        quoting=3,
    ).dropna()
    frame["target"] = (frame["label"] == "spam").astype(int)
    raw_count = len(frame)
    frame = frame.drop_duplicates(subset=["message"]).reset_index(drop=True)

    train, test = train_test_split(
        frame,
        test_size=0.2,
        stratify=frame["target"],
        random_state=42,
    )
    models = {
        "word_nb": build_nb(),
        "word_logistic": build_logistic(),
        "word_char_logistic": build_union_logistic(),
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores: dict[str, dict[str, dict[str, float]]] = {}
    for name, model in models.items():
        scores = cross_validate(
            model,
            train["message"],
            train["target"],
            cv=cv,
            scoring={
                "accuracy": "accuracy",
                "macro_f1": "f1_macro",
                "roc_auc": "roc_auc",
            },
        )
        cv_scores[name] = {
            metric.replace("test_", ""): {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)),
            }
            for metric, values in scores.items()
            if metric.startswith("test_")
        }
        print(name, cv_scores[name])

    selected_name = max(
        models,
        key=lambda name: cv_scores[name]["macro_f1"]["mean"],
    )
    selected = models[selected_name]
    selected.fit(train["message"], train["target"])
    probabilities = selected.predict_proba(test["message"])[:, 1]
    holdout = score_predictions(test["target"], probabilities)
    predictions = (probabilities >= 0.5).astype(int)
    errors = test[["label", "message"]].copy()
    errors["spam_probability"] = probabilities
    errors["prediction"] = np.where(predictions == 1, "spam", "ham")
    errors["correct"] = errors["label"] == errors["prediction"]
    errors.to_csv(REPORT_DIR / "spam_holdout_predictions.csv", index=False)

    plot_confusion(
        test["target"], probabilities, FIG_DIR / "spam_confusion_matrix.png"
    )
    metrics = {
        "dataset": {
            "raw_rows": raw_count,
            "unique_rows": len(frame),
            "spam": int(frame["target"].sum()),
            "ham": int((1 - frame["target"]).sum()),
            "train_size": len(train),
            "test_size": len(test),
            "source_doi": "10.24432/C5CC84",
            "license": "CC BY 4.0",
        },
        "cross_validation": cv_scores,
        "selected_model": selected_name,
        "temporal_holdout": holdout,
        "false_negatives": int(((test["target"] == 1) & (predictions == 0)).sum()),
        "false_positives": int(((test["target"] == 0) & (predictions == 1)).sum()),
        "operational_gate": {
            "high_block_threshold": 0.8,
            "review_threshold": 0.5,
            "high_risk_block_rate": float((probabilities >= 0.8).mean()),
            "blocked_message_spam_precision": float(
                test.loc[probabilities >= 0.8, "target"].mean()
            ),
            "spam_block_recall": float(
                ((probabilities >= 0.8) & (test["target"] == 1)).sum()
                / max(1, (test["target"] == 1).sum())
            ),
            "manual_review_rate": float(
                ((probabilities >= 0.5) & (probabilities < 0.8)).mean()
            ),
        },
    }
    (REPORT_DIR / "spam_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    final_model = models[selected_name]
    final_model.fit(frame["message"], frame["target"])
    artifact = {
        "pipeline": final_model,
        "metadata": {
            "version": "sms-spam-hybrid-tfidf-1.0",
            "trained_at": datetime.now().isoformat(timespec="seconds"),
            "training_rows": len(frame),
            "source": "UCI SMS Spam Collection v.1",
            "license": "CC BY 4.0",
        },
    }
    joblib.dump(artifact, MODEL_DIR / "sms_spam.joblib")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
