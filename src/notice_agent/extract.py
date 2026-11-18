"""Deterministic information extraction used by the agent's tools."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

DATE_PATTERNS = [
    re.compile(
        r"(?P<year>20\d{2})\s*[年./-]\s*(?P<month>1[0-2]|0?[1-9])\s*[月./-]\s*"
        r"(?P<day>3[01]|[12]\d|0?[1-9])\s*日?"
    ),
    re.compile(
        r"(?<!20\d{2}[年./-])(?P<month>1[0-2]|0?[1-9])\s*月\s*"
        r"(?P<day>3[01]|[12]\d|0?[1-9])\s*日"
    ),
]
TIME_PATTERN = re.compile(
    r"(?P<hour>[01]?\d|2[0-3])\s*[:：]\s*(?P<minute>[0-5]\d)"
)
DEADLINE_CUES = re.compile(
    r"截止|截至|之前|以前|前完成|前提交|前报名|前交|结束|"
    r"报名时间|报名日期|提交时间|申请时间|开放时间"
)
ACTION_CUES = re.compile(
    r"报名|提交|申请|登录|参加|完成|核对|缴费|交至|发送|打印|下载|"
    r"确认|填报|上传|携带|预约|退费|退改选|领取|申报|推荐"
)
AMBIGUOUS_TIME = re.compile(
    r"另行通知|待定|另行公布|本周|下周|近期|届时|以通知为准|查看附件|见附件"
)
SECURITY_FLAGS = {
    "索取验证码": re.compile(r"验证码|动态口令|短信码"),
    "索取身份证明": re.compile(r"学生证号|身份证号|银行卡号|密码"),
    "要求向陌生账号提交": re.compile(r"陌生账号|私人账户|向.{0,6}转账|汇款"),
}
MATERIAL_TERMS = [
    "报名表",
    "申请表",
    "成绩单",
    "证明材料",
    "承诺书",
    "学生证",
    "身份证",
    "作品",
    "论文",
    "查重报告",
    "个人陈述",
    "报名材料",
    "截图",
]
HIGH_IMPACT_CATEGORIES = {"考试考务", "学籍事务", "升学选拔", "毕业创新", "课程辅修"}


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentence_for_span(text: str, start: int, end: int) -> str:
    left = max(text.rfind(mark, 0, start) for mark in "。！？；\n") + 1
    right_candidates = [pos for mark in "。！？；\n" if (pos := text.find(mark, end)) >= 0]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return text[left:right].strip()


def extract_dates(text: str, reference_date: date) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            year = int(match.groupdict().get("year") or reference_date.year)
            month = int(match.group("month"))
            day = int(match.group("day"))
            try:
                parsed = date(year, month, day)
            except ValueError:
                continue
            sentence = _sentence_for_span(text, match.start(), match.end())
            time_match = TIME_PATTERN.search(sentence)
            local_context = text[max(0, match.start() - 18) : min(len(text), match.end() + 10)]
            deadline_sentence = bool(DEADLINE_CUES.search(local_context))
            found.append(
                {
                    "date": parsed.isoformat(),
                    "time": (
                        f"{int(time_match.group('hour')):02d}:{time_match.group('minute')}"
                        if time_match
                        else None
                    ),
                    "sentence": sentence,
                    "deadline_cue": deadline_sentence,
                }
            )
            occupied.append((match.start(), match.end()))
    return sorted(found, key=lambda item: (item["date"], item["time"] or "23:59"))


def choose_deadline(dates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not dates:
        return None
    cued = [item for item in dates if item["deadline_cue"]]
    pool = cued or dates
    # A "from ... to ..." range describes the final date as the deadline.
    return max(pool, key=lambda item: (item["date"], item["time"] or "23:59"))


def extract_actions(text: str) -> list[str]:
    chunks = re.split(r"[。！？；\n]+", text)
    actions: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip(" ，,、")
        chunk = re.sub(
            r"^(?:【[^】]{1,12}】)?关于[^：:]{0,70}(?:通知|公告)[：:]\s*",
            "",
            chunk,
        )
        if "：" in chunk or ":" in chunk:
            separator = "：" if "：" in chunk else ":"
            prefix, suffix = chunk.split(separator, 1)
            if len(prefix) > 8 and ACTION_CUES.search(suffix):
                chunk = suffix.strip()
        if 4 <= len(chunk) <= 90 and ACTION_CUES.search(chunk):
            if chunk not in actions:
                actions.append(chunk)
    return actions[:5]


def extract_materials(text: str) -> list[str]:
    return [term for term in MATERIAL_TERMS if term in text]


def extract_audience(text: str) -> str:
    patterns = [
        r"(20\d{2}级[^，。；\s]{0,12}(?:学生|本科生|同学))",
        r"((?:全体|全日制|应届|在校)?(?:本科|专科|本科|高职)?(?:毕业生|学生|同学))",
        r"(参赛队|申请人|报名者)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "未明确"


def priority_for(deadline: str | None, reference_date: date) -> str:
    if not deadline:
        return "unknown"
    deadline_date = date.fromisoformat(deadline)
    days = (deadline_date - reference_date).days
    if days < 0:
        return "expired"
    if days <= 2:
        return "high"
    if days <= 7:
        return "medium"
    if days <= 30:
        return "medium"
    return "low"


def extract_notice(
    text: str, reference_date: date | None = None
) -> dict[str, Any]:
    reference_date = reference_date or date.today()
    text = _normalize_spaces(text)
    dates = extract_dates(text, reference_date)
    deadline = choose_deadline(dates)
    security_flags = [
        label for label, pattern in SECURITY_FLAGS.items() if pattern.search(text)
    ]
    ambiguous_time = bool(AMBIGUOUS_TIME.search(text))
    actions = extract_actions(text)
    return {
        "deadline": deadline,
        "all_dates": dates,
        "actions": actions,
        "materials": extract_materials(text),
        "audience": extract_audience(text),
        "security_flags": security_flags,
        "ambiguous_time": ambiguous_time,
        "extraction_notes": [
            note
            for note in [
                "未找到明确截止日期" if deadline is None else "",
                "文本包含待定或需查看附件的时间信息" if ambiguous_time else "",
                "存在敏感信息索取风险，禁止自动执行" if security_flags else "",
            ]
            if note
        ],
        "priority": priority_for(deadline["date"] if deadline else None, reference_date),
    }


def deadline_local_date(deadline: dict[str, Any] | None) -> date | None:
    if not deadline:
        return None
    return date.fromisoformat(deadline["date"])


def deadline_datetime(deadline: dict[str, Any] | None) -> datetime | None:
    if not deadline:
        return None
    raw = deadline["date"]
    if deadline.get("time"):
        raw = f"{raw}T{deadline['time']}:00"
    return datetime.fromisoformat(raw)


def one_week_ago(reference_date: date) -> date:
    return reference_date - timedelta(days=7)
