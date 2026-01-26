from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional, Callable

from faster_whisper import WhisperModel

from utils.chunking import format_timestamp

SUPPORTED_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus"}


@dataclass
class TranscriptionResult:
    speaker: str
    segments: List[Dict[str, Any]]
    text: str


def list_audio_files(audio_dir: Path) -> List[Path]:
    return sorted(
        [p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    )


def normalize_audio(input_path: Path, work_dir: Path) -> Path:
    output_path = work_dir / f"{input_path.stem}_16k.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path


def load_model(model_name: str, device: str, compute_type: str) -> WhisperModel:
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_file(
    model: WhisperModel,
    audio_path: Path,
    speaker: str,
    language: Optional[str] = None,
) -> TranscriptionResult:
    segments_iter, _info = model.transcribe(
        str(audio_path),
        beam_size=5,
        language=language,
        vad_filter=True,
    )

    segments: List[Dict[str, Any]] = []
    lines: List[str] = []

    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue
        start = float(seg.start)
        end = float(seg.end)
        segments.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": text,
        })
        ts = format_timestamp(start, always_hours=True)
        lines.append(f"[{ts}] {text}")

    return TranscriptionResult(speaker=speaker, segments=segments, text="\n".join(lines))


def transcribe_directory(
    audio_dir: Path,
    model_name: str,
    device: str,
    compute_type: str,
    language: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> List[TranscriptionResult]:
    audio_files = list_audio_files(audio_dir)
    results: List[TranscriptionResult] = []

    if not audio_files:
        return results

    model = load_model(model_name, device, compute_type)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        total = len(audio_files)
        for idx, audio_path in enumerate(audio_files, start=1):
            speaker = audio_path.stem
            normalized = normalize_audio(audio_path, tmp_dir)
            result = transcribe_file(model, normalized, speaker, language=language)
            results.append(result)
            if progress_cb:
                progress_cb(idx, total, speaker)

    return results


def merge_segments(results: Iterable[TranscriptionResult]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for result in results:
        merged.extend(result.segments)
    merged.sort(key=lambda s: (s.get("start", 0), s.get("speaker", "")))
    return merged


def merged_transcript_text(segments: Iterable[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for seg in segments:
        ts = format_timestamp(float(seg.get("start", 0)), always_hours=True)
        speaker = seg.get("speaker", "Speaker")
        text = seg.get("text", "").strip()
        if not text:
            continue
        lines.append(f"[{ts}] {speaker}: {text}")
    return "\n".join(lines)


def save_segments_json(path: Path, segments: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
