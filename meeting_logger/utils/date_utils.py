from __future__ import annotations

import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_date_str(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def date_from_path(path: Path) -> Optional[date]:
    match = DATE_RE.search(path.name)
    if not match:
        return None
    return parse_date_str(match.group(0))


def determine_date(cli_date: Optional[str], audio_dir: Path) -> date:
    if cli_date:
        parsed = parse_date_str(cli_date)
        if parsed:
            return parsed

    folder_date = date_from_path(audio_dir)
    if folder_date:
        return folder_date

    latest_mtime = None
    for p in audio_dir.iterdir():
        if p.is_file():
            mtime = p.stat().st_mtime
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

    if latest_mtime is None:
        return datetime.now().date()

    return datetime.fromtimestamp(latest_mtime).date()


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")
