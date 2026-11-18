#!/usr/bin/env python3
"""Train and evaluate the Chinese campus-notice classifier."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_validate,
    train_test_split,
)
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notice_agent.classifier import apply_category_guard  # noqa: E402

DATA_PATH = ROOT / "data" / "processed" / "notice_categories.csv"
ARTIFACT_DIR = ROOT / "artifacts"
MODEL_DIR = ARTIFACT_DIR / "models"
FIG_DIR = ARTIFACT_DIR / "figures"
REPORT_DIR = ARTIFACT_DIR / "reports"

matplotlib.rcParams["font.sans-serif"] = ["Arial Unicode MS", "Songti SC", "STHeiti"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["figure.dpi"] = 160


def make_text(frame: pd.DataFrame, include_body: bool = True) -> pd.Series:
    title = frame["title"].fillna("").astype(str)
    if include_body:
        return title + " " + frame["body"].fillna("").astype(str)
    return title


def build_logistic_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(1, 4),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=3.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )


def build_nb_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(2, 4),
                    min_df=2,
                    max_features=30_000,
                    sublinear_tf=True,
                ),
            ),
            ("classifier", ComplementNB(alpha=0.3)),
        ]
    )


def metric_summary(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
    }


def cross_validate_model(
    model: Pipeline,
    features: pd.Series,
    target: pd.Series,
) -> dict[str, float]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_validate(
        model,
        features,
        target,
        cv=cv,
        scoring={"accuracy": "accuracy", "macro_f1": "f1_macro", "weighted_f1": "f1_weighted"},
        n_jobs=1,
    )
    return {
        metric: {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)),
        }
        for metric, values in scores.items()
        if metric.startswith("test_")
    }


def plot_confusion(
    y_true: pd.Series, y_pred: np.ndarray, labels: list[str], output: Path
) -> None:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(8.4, 6.8))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels=labels, rotation=35, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("预测类别")
    ax.set_ylabel("真实类别")
    ax.set_title("时间外推测试集混淆矩阵")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(
                col,
                row,
                str(matrix[row, col]),
                ha="center",
                va="center",
                color="white" if matrix[row, col] > matrix.max() / 2 else "#172033",
                fontsize=10,
            )
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_distribution(frame: pd.DataFrame, output: Path) -> None:
    counts = frame["category"].value_counts()
    fig, ax = plt.subplots(figsize=(8.4, 4.3))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color="#2563eb")
    ax.set_xlabel("通知数量")
    ax.set_title("中文校园通知类别分布（去重后 n=118）")
    ax.grid(axis="x", alpha=0.2)
    for bar, value in zip(bars, counts.values[::-1]):
        ax.text(value + 0.5, bar.get_y() + bar.get_height() / 2, str(value), va="center")
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for directory in [MODEL_DIR, FIG_DIR, REPORT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(DATA_PATH).fillna("")
    labels = sorted(frame["category"].unique())
    cutoff = "2025-01-01"
    train = frame[frame["date"] < cutoff].copy()
    test = frame[frame["date"] >= cutoff].copy()
    if test["category"].nunique() != len(labels):
        raise RuntimeError("Temporal holdout does not contain every class")
    train["text"] = make_text(train)
    test["text"] = make_text(test)

    print(f"temporal split: train={len(train)}, test={len(test)}, cutoff={cutoff}")
    cv_results: dict[str, dict[str, dict[str, float]]] = {}
    models: dict[str, tuple[Pipeline, pd.Series]] = {
        "majority_baseline": (
            Pipeline([("classifier", DummyClassifier(strategy="most_frequent"))]),
            train["text"],
        ),
        "char_ngram_nb": (build_nb_pipeline(), train["text"]),
        "char_ngram_logreg_title_only": (
            build_logistic_pipeline(),
            train["title"],
        ),
        "char_ngram_logreg_title_body": (
            build_logistic_pipeline(),
            train["text"],
        ),
    }
    for name, (model, features) in models.items():
        cv_results[name] = cross_validate_model(model, features, train["category"])
        print(name, cv_results[name])

    selected_name = "char_ngram_logreg_title_body"
    selected, selected_features = models[selected_name]
    selected.fit(selected_features, train["category"])
    predictions = selected.predict(test["text"])
    probabilities = selected.predict_proba(test["text"]).max(axis=1)
    ml_metrics = metric_summary(test["category"], predictions)
    ml_metrics["macro_f1"] = float(
        f1_score(test["category"], predictions, average="macro", zero_division=0)
    )
    ml_metrics["weighted_f1"] = float(
        f1_score(test["category"], predictions, average="weighted", zero_division=0)
    )

    hybrid_results = [
        apply_category_guard(
            text,
            {
                "category": prediction,
                "confidence": confidence,
                "probabilities": {},
                "model_version": "notice-char-logreg-1.0",
            },
        )
        for text, prediction, confidence in zip(test["text"], predictions, probabilities)
    ]
    hybrid_predictions = np.array([item["category"] for item in hybrid_results])
    hybrid_probabilities = np.array([item["confidence"] for item in hybrid_results])
    hybrid_metrics = metric_summary(test["category"], hybrid_predictions)

    threshold = 0.55
    accepted = hybrid_probabilities >= threshold
    threshold_metrics = {
        "threshold": threshold,
        "coverage": float(accepted.mean()),
        "manual_review_rate": float(1 - accepted.mean()),
        "accepted_accuracy": (
            float(
                accuracy_score(
                    test.loc[accepted, "category"], hybrid_predictions[accepted]
                )
            )
            if accepted.any()
            else None
        ),
        "overall_accuracy": float(accuracy_score(test["category"], hybrid_predictions)),
    }

    predictions_frame = test[["id", "date", "title", "category"]].copy()
    predictions_frame["ml_prediction"] = predictions
    predictions_frame["ml_confidence"] = probabilities
    predictions_frame["hybrid_prediction"] = hybrid_predictions
    predictions_frame["hybrid_confidence"] = hybrid_probabilities
    predictions_frame["correct"] = (
        predictions_frame["category"] == predictions_frame["hybrid_prediction"]
    )
    predictions_frame["review_required"] = ~accepted
    predictions_frame.to_csv(REPORT_DIR / "temporal_holdout_predictions.csv", index=False)

    ml_report = classification_report(
        test["category"], predictions, labels=labels, output_dict=True, zero_division=0
    )
    hybrid_report = classification_report(
        test["category"],
        hybrid_predictions,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "dataset": {
            "total_unique": int(len(frame)),
            "classes": int(frame["category"].nunique()),
            "temporal_cutoff": cutoff,
            "train_size": int(len(train)),
            "test_size": int(len(test)),
            "class_counts": {
                key: int(value) for key, value in frame["category"].value_counts().items()
            },
        },
        "cross_validation": cv_results,
        "temporal_holdout": {
            "model": selected_name,
            "ml_only": {"metrics": ml_metrics, "per_class": ml_report},
            "hybrid": {"metrics": hybrid_metrics, "per_class": hybrid_report},
            "confidence_gate": threshold_metrics,
        },
    }
    (REPORT_DIR / "model_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    plot_confusion(
        test["category"],
        predictions,
        labels,
        FIG_DIR / "confusion_matrix_ml.png",
    )
    plot_confusion(
        test["category"],
        hybrid_predictions,
        labels,
        FIG_DIR / "confusion_matrix_hybrid.png",
    )
    plot_distribution(frame, FIG_DIR / "category_distribution.png")

    final_text = make_text(frame, include_body=True)
    final_model = build_logistic_pipeline()
    final_model.fit(final_text, frame["category"])
    artifact = {
        "pipeline": final_model,
        "metadata": {
            "version": "notice-char-logreg-1.0",
            "trained_at": datetime.now().isoformat(timespec="seconds"),
            "training_rows": int(len(frame)),
            "labels": labels,
            "features": "标题 + 正文；中文字符 1-4 gram TF-IDF；C=3；class_weight=balanced",
        },
    }
    model_path = MODEL_DIR / "notice_category.joblib"
    joblib.dump(artifact, model_path)
    print(json.dumps(metrics["temporal_holdout"], ensure_ascii=False, indent=2))
    print(f"wrote model: {model_path}")


if __name__ == "__main__":
    main()
