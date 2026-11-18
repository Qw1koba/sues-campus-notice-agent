#!/usr/bin/env python3
"""Convert the crawled public notices into a de-duplicated labelled corpus."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "sues_jwc_notices.jsonl"
OUT_PATH = ROOT / "data" / "processed" / "notice_categories.csv"

CATEGORY_RULES: list[tuple[str, str]] = [
    (
        "竞赛活动",
        r"竞赛|大赛|挑战赛|诗词大会|诵写讲|汇创青春|蓝桥杯|演讲大赛|书法大赛|"
        r"篆刻大赛|魅力汉语|获奖名单|成果展|参赛作品",
    ),
    (
        "考试考务",
        r"四、六级|CET|信息技术水平考试|考试|测试|补测|体质健康|口语",
    ),
    (
        "毕业创新",
        r"毕业设计|毕业论文|论文|创新实验|创新训练|创新创业训练|结题",
    ),
    (
        "学籍事务",
        r"成绩单|在读|学历|学位证明|转专业|插班生|学生人数|学籍",
    ),
    (
        "课程辅修",
        r"辅修|微专业|MOOC|智慧树|课表|选课|学生手册|在线课程",
    ),
    (
        "升学选拔",
        r"专项班|推免|免试攻读|研究生",
    ),
]


def label_notice(title: str) -> str:
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, title, flags=re.IGNORECASE):
            return category
    return "校务公告"


def main() -> None:
    records = [
        json.loads(line)
        for line in RAW_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    unique: dict[str, dict[str, str]] = {}
    for record in records:
        # Exact duplicate entries exist in the public list. Keep one copy and
        # record it in the report instead of allowing duplicate leakage.
        key = re.sub(r"\s+", "", record["title"]).lower()
        if key in unique:
            unique[key]["duplicate_of_url"] = record["url"]
            continue
        record["category"] = label_notice(record["title"])
        unique[key] = record

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "title", "date", "category", "url", "body", "duplicate_of_url"]
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for idx, record in enumerate(unique.values(), start=1):
            writer.writerow(
                {
                    **{field: record.get(field, "") for field in fields},
                    "id": f"N{idx:03d}",
                }
            )

    counts: dict[str, int] = {}
    for record in unique.values():
        counts[record["category"]] = counts.get(record["category"], 0) + 1
    print(f"raw={len(records)}, unique={len(unique)}")
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
