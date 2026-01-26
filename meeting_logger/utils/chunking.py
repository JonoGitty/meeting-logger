from __future__ import annotations

from typing import Iterable, List, Dict, Any


def format_timestamp(seconds: float, always_hours: bool = True) -> str:
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if always_hours or h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def chunk_text(text: str, max_chars: int = 1800) -> List[str]:
    if not text:
        return []

    parts: List[str] = []
    for paragraph in text.split("\n"):
        para = paragraph.strip()
        if not para:
            continue
        while len(para) > max_chars:
            parts.append(para[:max_chars])
            para = para[max_chars:]
        parts.append(para)

    if not parts:
        return []

    return parts


def group_segments_into_windows(
    segments: Iterable[Dict[str, Any]],
    chunk_minutes: int,
) -> List[Dict[str, Any]]:
    window_seconds = max(1, int(chunk_minutes)) * 60
    windows: Dict[int, List[Dict[str, Any]]] = {}

    for seg in segments:
        start = float(seg.get("start", 0))
        window_index = int(start // window_seconds)
        windows.setdefault(window_index, []).append(seg)

    if not windows:
        return []

    results: List[Dict[str, Any]] = []
    for index in sorted(windows.keys()):
        start = index * window_seconds
        end = (index + 1) * window_seconds
        range_label = f"{format_timestamp(start, always_hours=False)}-{format_timestamp(end, always_hours=False)}"
        results.append({
            "range": range_label,
            "segments": windows[index],
        })

    return results
