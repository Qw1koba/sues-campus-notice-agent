#!/usr/bin/env python3
"""Measure local end-to-end latency after warm-up."""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from notice_agent.agent import CampusNoticeAgent  # noqa: E402

TEXT = (
    "【教务处】2026年下半年全国大学英语四、六级考试报名将于"
    "11月20日17:00截止。请需要报名的本科生登录教务系统核对学籍信息"
    "并完成缴费，逾期不再补报。"
)


def main() -> None:
    agent = CampusNoticeAgent()
    agent.analyze(TEXT, reference_date=date(2026, 11, 18))
    durations = []
    for _ in range(60):
        started = time.perf_counter()
        result = agent.analyze(TEXT, reference_date=date(2026, 11, 18))
        durations.append((time.perf_counter() - started) * 1000)
        if result.status != "completed":
            raise RuntimeError("benchmark sample did not complete")
    durations.sort()
    metrics = {
        "runs": len(durations),
        "warmup_runs": 1,
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(durations[int(len(durations) * 0.95) - 1], 3),
        "mean_ms": round(statistics.mean(durations), 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    output = ROOT / "artifacts" / "reports" / "latency.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
