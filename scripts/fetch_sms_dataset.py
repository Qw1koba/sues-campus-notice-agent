#!/usr/bin/env python3
"""Download and verify the public UCI SMS Spam Collection."""

from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip"
SHA256 = "1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "external"


def main() -> None:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "SUES-Course-Project-Notice-Agent/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != SHA256:
        raise RuntimeError(f"checksum mismatch: expected {SHA256}, received {digest}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extract("SMSSpamCollection", OUTPUT_DIR)
        archive.extract("readme", OUTPUT_DIR)
    print(f"downloaded and verified {OUTPUT_DIR / 'SMSSpamCollection'}")


if __name__ == "__main__":
    main()
