#!/usr/bin/env python3
"""Run three deterministic demonstrations and save a text/JSON transcript."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notice_agent.agent import CampusNoticeAgent, write_ics, write_markdown  # noqa: E402

CASES = [
    {
        "id": "D01",
        "title": "四、六级考试报名通知",
        "text": (
            "【教务处】2026年下半年全国大学英语四、六级考试报名将于"
            "11月20日17:00截止。请需要报名的本科生登录教务系统核对学籍信息"
            "并完成缴费，逾期不再补报。"
        ),
    },
    {
        "id": "D02",
        "title": "创新实验项目申请通知",
        "text": (
            "关于申请创新实验项目的通知：本批次采用线上申请，"
            "具体开放时间、截止日期和材料要求另行通知。"
        ),
    },
    {
        "id": "D03",
        "title": "可疑中奖短信",
        "text": (
            "URGENT! You have won a 2000 prize. Call 09061701461 now to "
            "claim your reward. Txt STOP to opt out."
        ),
        "date": "2026-11-18",
    },
]


def main() -> None:
    output_dir = ROOT / "artifacts" / "demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    agent = CampusNoticeAgent()
    results = []
    for case in CASES:
        reference_date = date.fromisoformat(case.get("date", "2026-11-18"))
        result = agent.analyze(
            case["text"], title=case["title"], reference_date=reference_date
        )
        stem = case["id"]
        (output_dir / f"{stem}_result.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_markdown(result, output_dir / f"{stem}_checklist.md", case["title"])
        if (result.extraction or {}).get("deadline"):
            write_ics(result, output_dir / f"{stem}_deadline.ics", case["title"])
        results.append({"case": case, "result": result.to_dict()})

    (output_dir / "demo_transcript.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["# 演示记录", "", "运行日期：2026-11-18", ""]
    for item in results:
        case = item["case"]
        result = item["result"]
        lines.extend(
            [
                f"## {case['id']} {case['title']}",
                "",
                "输入：",
                "",
                f"> {case['text']}",
                "",
                f"状态：`{result['status']}`",
                "",
            ]
        )
        if result.get("classification"):
            lines.append(
                f"分类：{result['classification']['category']}，"
                f"置信度 {result['classification']['confidence']:.3f}"
            )
        if result.get("extraction") and result["extraction"].get("deadline"):
            deadline = result["extraction"]["deadline"]
            lines.append(
                f"截止：{deadline['date']} {deadline.get('time') or ''}".rstrip()
            )
        lines.extend(["", "行动清单：", ""])
        lines.extend(f"- [ ] {item}" for item in result.get("checklist", []))
        if result.get("review_reasons"):
            lines.extend(["", "需要确认："])
            lines.extend(f"- {reason}" for reason in result["review_reasons"])
        lines.extend(["", "执行轨迹：", ""])
        lines.extend(
            f"- {step['name']}：{step['result']}" for step in result.get("steps", [])
        )
        lines.append("")
    (output_dir / "demo_transcript.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(f"wrote {output_dir / 'demo_transcript.md'}")


if __name__ == "__main__":
    main()
