"""End-to-end workflow for the Campus Notice Action Agent."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .classifier import cascade_predict
from .extract import extract_notice
from .ingest import read_notice_file
from .sms_spam import optional_spam_check

CONFIDENCE_THRESHOLD = 0.55


@dataclass
class AgentResult:
    trace_id: str
    status: str
    input_length: int
    classification: dict[str, Any] | None
    extraction: dict[str, Any] | None
    spam_check: dict[str, Any]
    review_required: bool
    review_reasons: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    steps: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "input_length": self.input_length,
            "classification": self.classification,
            "extraction": self.extraction,
            "spam_check": self.spam_check,
            "review_required": self.review_required,
            "review_reasons": self.review_reasons,
            "checklist": self.checklist,
            "steps": self.steps,
            "error": self.error,
        }


def _trace_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _clean_title(title: str | None, text: str) -> str:
    if title and title.strip():
        return title.strip()[:120]
    first = re.split(r"[。！？\n]", text, maxsplit=1)[0]
    return first[:80]


class CampusNoticeAgent:
    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = model_path

    def analyze(
        self,
        text: str,
        *,
        title: str | None = None,
        reference_date: date | None = None,
    ) -> AgentResult:
        text = (text or "").strip()
        trace_id = _trace_id(text)
        steps: list[dict[str, str]] = []
        if len(text) < 8:
            steps.append({"name": "输入校验", "result": "失败：文本过短"})
            return AgentResult(
                trace_id=trace_id,
                status="rejected",
                input_length=len(text),
                classification=None,
                extraction=None,
                spam_check={"applicable": False, "reason": "输入未通过校验"},
                review_required=True,
                review_reasons=["输入为空或长度不足 8 个字符"],
                steps=steps,
                error="输入为空或无法识别",
            )
        if len(text) > 20_000:
            text = text[:20_000]
        steps.append({"name": "输入校验", "result": "通过；使用本地确定性规则和模型"})

        spam_check = optional_spam_check(text)
        if spam_check.get("applicable"):
            steps.append(
                {
                    "name": "垃圾短信门禁",
                    "result": (
                        f"{spam_check['risk']}风险，"
                        f"p={spam_check['spam_probability']:.3f}"
                    ),
                }
            )
            if spam_check["spam_probability"] >= 0.8:
                return AgentResult(
                    trace_id=trace_id,
                    status="blocked_spam",
                    input_length=len(text),
                    classification=None,
                    extraction=None,
                    spam_check=spam_check,
                    review_required=False,
                    review_reasons=[],
                    checklist=[
                        "不要点击链接、回复短信或提供验证码",
                        "通过机构官网或官方客服独立核验",
                        "必要时向运营商或学校安全部门报告",
                    ],
                    steps=steps,
                )
            if spam_check["spam_probability"] >= 0.5:
                steps.append(
                    {"name": "垃圾短信门禁", "result": "中风险，进入人工确认"}
                )
        else:
            steps.append(
                {
                    "name": "垃圾短信门禁",
                    "result": spam_check.get("reason", "不适用"),
                }
            )

        notice_title = _clean_title(title, text)
        model_text = f"{notice_title} {text}"[:2500]
        classification = cascade_predict(model_text, self.model_path)
        steps.append(
            {
                "name": "机器学习分流",
                "result": (
                    f"{classification['category']}，置信度 "
                    f"{classification['confidence']:.3f}"
                ),
            }
        )

        extraction = extract_notice(text, reference_date=reference_date)
        steps.append(
            {
                "name": "结构化抽取",
                "result": (
                    f"截止 {extraction['deadline']['date'] if extraction['deadline'] else '未识别'}，"
                    f"{len(extraction['actions'])} 条行动"
                ),
            }
        )

        review_reasons: list[str] = []
        if spam_check.get("spam_probability", 0) >= 0.5:
            review_reasons.append("垃圾短信风险处于不确定区间")
        if classification["confidence"] < CONFIDENCE_THRESHOLD:
            review_reasons.append(
                f"分类置信度 {classification['confidence']:.3f} 低于阈值 {CONFIDENCE_THRESHOLD:.2f}"
            )
        if not extraction["deadline"]:
            review_reasons.append("未找到明确截止日期")
        if extraction["ambiguous_time"] and not extraction["deadline"]:
            review_reasons.append("截止时间待定或依赖附件")
        if extraction["security_flags"]:
            review_reasons.append("检测到敏感信息或资金操作风险")
        if not extraction["actions"] and classification["category"] != "校务公告":
            review_reasons.append("业务通知未抽取到可执行动作")

        steps.append(
            {
                "name": "安全复核",
                "result": "需要人工确认" if review_reasons else "可生成行动清单",
            }
        )
        checklist = self._make_checklist(notice_title, classification, extraction)
        review_required = bool(review_reasons)
        return AgentResult(
            trace_id=trace_id,
            status="review_required" if review_required else "completed",
            input_length=len(text),
            classification=classification,
            extraction=extraction,
            spam_check=spam_check,
            review_required=review_required,
            review_reasons=review_reasons,
            checklist=checklist,
            steps=steps,
        )

    def analyze_file(
        self,
        path: str | Path,
        *,
        reference_date: date | None = None,
    ) -> AgentResult:
        text = read_notice_file(path)
        return self.analyze(text, title=Path(path).stem, reference_date=reference_date)

    @staticmethod
    def _make_checklist(
        title: str,
        classification: dict[str, Any],
        extraction: dict[str, Any],
    ) -> list[str]:
        checklist = [f"阅读原文并核对通知对象：{extraction['audience']}"]
        if extraction["deadline"]:
            deadline = extraction["deadline"]
            suffix = f" {deadline['time']}" if deadline.get("time") else ""
            checklist.append(f"截止时间：{deadline['date']}{suffix}")
        else:
            checklist.append("先向发布方确认截止时间，勿按猜测日期安排")
        if extraction["materials"]:
            checklist.append(f"准备材料：{'、'.join(extraction['materials'])}")
        for action in extraction["actions"][:3]:
            checklist.append(f"执行：{action}")
        checklist.append(f"归档分类：{classification['category']}")
        if extraction["security_flags"]:
            checklist.append("停止自动操作；通过官方渠道人工核验")
        return checklist


def write_ics(result: AgentResult, output_path: str | Path, title: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    deadline = (result.extraction or {}).get("deadline")
    if not deadline:
        raise ValueError("没有可写入日历的截止时间")
    start_raw = deadline["date"] + "T" + (deadline.get("time") or "09:00") + ":00"
    start = datetime.fromisoformat(start_raw)
    end = start + timedelta(minutes=30)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def fmt(value: datetime) -> str:
        return value.strftime("%Y%m%dT%H%M%S")

    safe_title = title.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
    description = "；".join(result.checklist).replace("\\", "\\\\").replace(",", "\\,")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SUES//Campus Notice Action Agent//CN",
        "BEGIN:VEVENT",
        f"UID:{result.trace_id}@notice-agent.local",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        f"SUMMARY:{safe_title}",
        f"DESCRIPTION:{description}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        "DESCRIPTION:校园通知截止提醒",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    output.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return output


def write_markdown(result: AgentResult, output_path: str | Path, title: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    classification = result.classification or {}
    extraction = result.extraction or {}
    lines = [
        f"# {title}",
        "",
        f"- 状态：{result.status}",
        f"- 分类：{classification.get('category', '未分类')}",
        f"- 置信度：{classification.get('confidence', 0):.3f}",
        f"- 优先级：{extraction.get('priority', 'unknown')}",
        "",
        "## 行动清单",
        "",
        *[f"- [ ] {item}" for item in result.checklist],
        "",
        "## 需要人工确认",
        "",
        *([f"- {reason}" for reason in result.review_reasons] or ["- 无"]),
        "",
        "> 系统只生成提醒，不代为报名、缴费或提交材料。",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
