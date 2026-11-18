"""Command-line entry point for the Campus Notice Action Agent."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .agent import CampusNoticeAgent, write_ics, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校讯行动助手")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="直接输入通知正文")
    source.add_argument("--file", help="通知文件：.txt/.docx/.pdf")
    parser.add_argument("--title", help="通知标题")
    parser.add_argument("--date", help="参考日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--output-dir", default="artifacts/demo", help="输出目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    reference_date = date.fromisoformat(args.date) if args.date else None
    agent = CampusNoticeAgent()
    if args.file:
        result = agent.analyze_file(args.file, reference_date=reference_date)
        title = args.title or Path(args.file).stem
    else:
        result = agent.analyze(
            args.text,
            title=args.title,
            reference_date=reference_date,
        )
        title = args.title or (args.text[:40] if args.text else "通知")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, output_dir / "action_checklist.md", title)
    if (result.extraction or {}).get("deadline"):
        write_ics(result, output_dir / "deadline.ics", title)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"状态：{result.status}")
        if result.classification:
            print(
                f"分类：{result.classification['category']} "
                f"({result.classification['confidence']:.3f})"
            )
        if result.extraction and result.extraction.get("deadline"):
            deadline = result.extraction["deadline"]
            print(f"截止：{deadline['date']} {deadline.get('time') or ''}")
        print("行动清单：")
        for item in result.checklist:
            print(f"  - {item}")
        if result.review_reasons:
            print("需要确认：")
            for reason in result.review_reasons:
                print(f"  - {reason}")
        print(f"输出目录：{output_dir.resolve()}")


if __name__ == "__main__":
    main()
