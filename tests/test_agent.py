from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from docx import Document

from notice_agent.agent import CampusNoticeAgent, write_ics
from notice_agent.ingest import UnsafeDocumentError, read_notice_file


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = CampusNoticeAgent()

    def test_extracts_notice_deadline_and_category(self) -> None:
        result = self.agent.analyze(
            "【教务处】2026年下半年全国大学英语四、六级考试报名将于"
            "11月20日17:00截止。请需要报名的本科生登录教务系统并完成缴费。",
            reference_date=date(2026, 11, 18),
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.classification["category"], "考试考务")
        self.assertEqual(result.extraction["deadline"]["date"], "2026-11-20")
        self.assertEqual(result.extraction["deadline"]["time"], "17:00")

    def test_vague_notice_requires_review(self) -> None:
        result = self.agent.analyze(
            "关于创新实验项目申请的通知：开放时间和材料要求另行通知。",
            reference_date=date(2026, 11, 18),
        )
        self.assertTrue(result.review_required)
        self.assertEqual(result.status, "review_required")

    def test_deadline_range_uses_last_date(self) -> None:
        result = self.agent.analyze(
            "竞赛报名时间为4月1日至4月12日，请提交报名表。",
            reference_date=date(2026, 3, 20),
        )
        self.assertEqual(result.extraction["deadline"]["date"], "2026-04-12")

    def test_spam_is_blocked_before_actions(self) -> None:
        result = self.agent.analyze(
            "URGENT! You have won a 2000 prize. Call 09061701461 now to claim "
            "your reward. Txt STOP to opt out."
        )
        self.assertEqual(result.status, "blocked_spam")
        self.assertIsNone(result.extraction)
        self.assertTrue(any("验证码" in item for item in result.checklist))

    def test_docx_ingestion_and_ics_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            docx_path = root / "notice.docx"
            document = Document()
            document.add_paragraph("关于转专业工作的通知")
            document.add_paragraph("请在5月8日前提交申请表和成绩单。")
            document.save(docx_path)
            text = read_notice_file(docx_path)
            self.assertIn("转专业", text)
            result = self.agent.analyze(
                text, title="转专业通知", reference_date=date(2026, 4, 1)
            )
            ics = write_ics(result, root / "deadline.ics", "转专业通知")
            content = ics.read_text(encoding="utf-8")
            self.assertIn("DTSTART:20260508", content)
            self.assertIn("BEGIN:VALARM", content)

    def test_unsafe_docx_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "unsafe.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.xml", "<unsafe/>")
            with self.assertRaises(UnsafeDocumentError):
                read_notice_file(path)


if __name__ == "__main__":
    unittest.main()
