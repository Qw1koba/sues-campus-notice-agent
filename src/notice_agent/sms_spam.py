"""Optional English SMS spam gate."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPAM_MODEL = ROOT / "artifacts" / "models" / "sms_spam.joblib"


def mostly_ascii(text: str, threshold: float = 0.82) -> bool:
    visible = re.sub(r"\s", "", text)
    if not visible:
        return False
    ascii_count = sum(ord(char) < 128 for char in visible)
    return ascii_count / len(visible) >= threshold


class SmsSpamClassifier:
    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path or DEFAULT_SPAM_MODEL)
        if not self.model_path.exists():
            raise FileNotFoundError(f"垃圾短信模型不存在：{self.model_path}")
        artifact = joblib.load(self.model_path)
        self.pipeline = artifact["pipeline"]
        self.metadata = artifact.get("metadata", {})

    def predict(self, text: str) -> dict[str, Any]:
        probability = float(self.pipeline.predict_proba([text])[0, 1])
        if probability >= 0.8:
            risk = "high"
        elif probability >= 0.5:
            risk = "medium"
        else:
            risk = "low"
        return {
            "applicable": True,
            "spam_probability": round(probability, 6),
            "risk": risk,
            "model_version": self.metadata.get("version", "unknown"),
        }


@lru_cache(maxsize=4)
def _load_spam_classifier(model_path: str) -> SmsSpamClassifier:
    return SmsSpamClassifier(model_path)


def optional_spam_check(
    text: str, model_path: str | Path | None = None
) -> dict[str, Any]:
    if not mostly_ascii(text):
        return {
            "applicable": False,
            "reason": "文本不是英文/ASCII 短信；中文安全由本地敏感信息规则处理",
        }
    try:
        resolved_path = str(Path(model_path or DEFAULT_SPAM_MODEL).resolve())
        return _load_spam_classifier(resolved_path).predict(text)
    except FileNotFoundError:
        return {"applicable": False, "reason": "垃圾短信模型未安装"}
