# Third-party components and reused skill review

## Anthropic `docx` skill (instruction-level reuse)

- Source: <https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/docx>
- Version: Git commit `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` (inspected 2026-11-18)
- License: Apache License 2.0 (`LICENSE.txt` in that skill directory).
- Local license copy: `licenses/anthropic-docx-skill-LICENSE.txt`.
- What was reused: the guidance to treat a DOCX as an untrusted ZIP archive, validate it,
  and verify extracted output. The project does not redistribute the skill's scripts.
- Integration work: `src/notice_agent/ingest.py` implements a small independent reader with
  a 5 MB input limit, 2,000 archive-entry limit, 30 MB uncompressed-size limit, path-traversal
  rejection, active-content suffix rejection, paragraph/table extraction, and tests.
- Behavior check: `tests/test_agent.py` reads a normal DOCX and rejects a ZIP containing
  `../escape.xml`. The prototype never executes macros or embedded files.
- Limitations: `.doc` is not accepted; scanned PDFs require OCR and are rejected when no text
  can be extracted. Only explicit user-selected local files are read.

## UCI SMS Spam Collection v.1

- Source: <https://doi.org/10.24432/C5CC84>
- License: CC BY 4.0.
- Use: external benchmark for the optional English SMS spam gate.

## Python packages

The exact versions are pinned in `requirements.txt`. Principal packages are scikit-learn
(BSD-3-Clause), pandas (BSD-3-Clause), NumPy (BSD-3-Clause), Matplotlib (PSF-based),
python-docx (MIT), pypdf (BSD-3-Clause), BeautifulSoup (MIT), ReportLab (BSD-style), and
joblib (BSD-3-Clause). They are used as libraries and were not modified.
