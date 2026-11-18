"""Chinese notice category classifier and confidence handling."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "artifacts" / "models" / "notice_category.joblib"

RULE_CATEGORIES: list[tuple[str, str]] = [
    ("竞赛活动", r"竞赛|大赛|挑战赛|诗词|诵写讲|蓝桥杯|汇创|作品"),
    ("考试考务", r"考试|四、六级|CET|测试|补测|体质"),
    ("毕业创新", r"毕业设计|毕业论文|创新实验|创新训练|结题"),
    ("学籍事务", r"成绩单|学历|学位|转专业|插班生|学籍"),
    ("课程辅修", r"辅修|微专业|MOOC|智慧树|选课|课表"),
    ("升学选拔", r"专项班|推免|免试攻读|研究生"),
]

GUARD_RULES: list[tuple[str, str]] = [
    ("升学选拔", r"专项班|推免|免试攻读|研究生招生"),
    ("毕业创新", r"毕业设计|毕业论文|论文初稿|创新实验|创新训练|创新创业训练|结题"),
    ("课程辅修", r"辅修|微专业|选课|退改选|MOOC|智慧树|课表|在线课程|学生手册"),
    ("竞赛活动", r"竞赛|大赛|挑战赛|诗词大会|诵写讲|蓝桥杯|汇创青春|作品征集"),
    ("考试考务", r"考试|四、六级|CET|测试|补测|体质健康|口语"),
    ("学籍事务", r"转专业|插班生|办理成绩单|成绩单打印|在读证明|学历|学位证明|学籍"),
    ("校务公告", r"校历|自习|系统维护|问卷|宣讲会|招聘会|公告|开放安排"),
]


def _rule_category(text: str) -> tuple[str, float]:
    for category, pattern in RULE_CATEGORIES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return category, 0.35
    return "校务公告", 0.35


def apply_category_guard(
    text: str, model_result: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Apply a high-precision business lexicon after the learned classifier.

    The learned model handles ambiguous paraphrases. Explicit taxonomy terms
    are deterministic and serve as a guard for label drift and newly named
    programmes.  The original model probability remains visible for audit.
    """

    result = dict(model_result or {})
    model_category = result.get("category")
    model_confidence = float(result.get("confidence", 0.0))
    for category, pattern in GUARD_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {
                **result,
                "category": category,
                "model_category": model_category,
                "model_confidence": round(model_confidence, 6),
                "confidence": round(max(model_confidence, 0.88), 6),
                "confidence_source": "model+rule_guard",
                "guard_category": category,
            }
    return {
        **result,
        "model_category": model_category,
        "model_confidence": round(model_confidence, 6),
        "confidence_source": "model",
    }


class NoticeClassifier:
    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path or DEFAULT_MODEL_PATH)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"模型不存在：{self.model_path}。请先运行 scripts/train_models.py"
            )
        artifact = joblib.load(self.model_path)
        self.pipeline = artifact["pipeline"]
        self.classes = list(self.pipeline.classes_)
        self.metadata = artifact.get("metadata", {})

    def predict(self, text: str) -> dict[str, Any]:
        probabilities = self.pipeline.predict_proba([text])[0]
        best_index = int(probabilities.argmax())
        category = str(self.pipeline.classes_[best_index])
        confidence = float(probabilities[best_index])
        distribution = {
            str(label): round(float(probability), 6)
            for label, probability in sorted(
                zip(self.pipeline.classes_, probabilities),
                key=lambda item: item[1],
                reverse=True,
            )
        }
        return {
            "category": category,
            "confidence": round(confidence, 6),
            "probabilities": distribution,
            "model_version": self.metadata.get("version", "unknown"),
        }


@lru_cache(maxsize=4)
def _load_classifier(model_path: str) -> NoticeClassifier:
    return NoticeClassifier(model_path)


def cascade_predict(
    text: str, model_path: str | Path | None = None, use_guards: bool = True
) -> dict[str, Any]:
    resolved_path = str(Path(model_path or DEFAULT_MODEL_PATH).resolve())
    try:
        result = _load_classifier(resolved_path).predict(text)
    except FileNotFoundError:
        category, confidence = _rule_category(text)
        result = {
            "category": category,
            "confidence": confidence,
            "probabilities": {category: confidence},
            "model_version": "rule-fallback",
        }
    return apply_category_guard(text, result) if use_guards else result
