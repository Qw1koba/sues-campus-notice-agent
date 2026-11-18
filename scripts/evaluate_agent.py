#!/usr/bin/env python3
"""Evaluate structured extraction and review gating on boundary cases."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notice_agent.agent import CampusNoticeAgent  # noqa: E402

CASES_PATH = ROOT / "data" / "processed" / "boundary_cases.jsonl"
OUTPUT_CSV = ROOT / "artifacts" / "reports" / "boundary_case_results.csv"
OUTPUT_JSON = ROOT / "artifacts" / "reports" / "agent_metrics.json"


def main() -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    agent = CampusNoticeAgent()
    rows: list[dict[str, object]] = []
    for case in cases:
        result = agent.analyze(
            case["text"],
            title=case["text"][:40],
            reference_date=date(2026, 11, 18),
        )
        extraction = result.extraction or {}
        deadline = extraction.get("deadline") or {}
        category = (result.classification or {}).get("category")
        rows.append(
            {
                "id": case["id"],
                "expected_category": case["expected_category"],
                "predicted_category": category,
                "category_correct": category == case["expected_category"],
                "expected_deadline": case["expected_deadline"],
                "predicted_deadline": deadline.get("date"),
                "deadline_correct": deadline.get("date") == case["expected_deadline"],
                "expected_review": case["expected_review"],
                "predicted_review": result.review_required,
                "review_correct": result.review_required == case["expected_review"],
                "confidence": (result.classification or {}).get("confidence"),
                "review_reasons": "；".join(result.review_reasons),
                "status": result.status,
            }
        )

    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    deadline_applicable = frame["expected_deadline"].notna()
    metrics = {
        "cases": int(len(frame)),
        "category_accuracy": float(frame["category_correct"].mean()),
        "deadline_exact_accuracy": float(
            frame.loc[deadline_applicable, "deadline_correct"].mean()
        ),
        "deadline_applicable_cases": int(deadline_applicable.sum()),
        "review_decision_accuracy": float(frame["review_correct"].mean()),
        "false_auto_acceptance": int(
            ((frame["expected_review"]) & (~frame["predicted_review"])).sum()
        ),
        "unnecessary_review": int(
            ((~frame["expected_review"]) & (frame["predicted_review"])).sum()
        ),
        "end_to_end_task_success": float(
            (
                frame["category_correct"]
                & frame["deadline_correct"]
                & frame["review_correct"]
            ).mean()
        ),
    }
    OUTPUT_JSON.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(frame.to_string(index=False))
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
