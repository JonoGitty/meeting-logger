from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

from transcriber.whisper_runner import (
    transcribe_directory,
    merge_segments,
    merged_transcript_text,
    save_segments_json,
)
from summariser.meeting_summariser import summarise_meeting, timeline_summary
from notion.notion_uploader import upload_to_notion
from utils.date_utils import determine_date, format_date
from utils.chunking import group_segments_into_windows
from research.researcher import (
    extract_research_requests,
    normalize_trigger_text,
    run_research,
)


@dataclass
class PipelineConfig:
    audio_dir: Path
    project: Optional[str] = None
    meeting_title: Optional[str] = None
    date_override: Optional[str] = None
    chunk_minutes: int = 5
    model: str = "small"
    recording_url: Optional[str] = None
    upload_notion: bool = False
    summarise: bool = True
    notion_enabled: bool = True
    openai_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    notion_token: Optional[str] = None
    notion_database_id: Optional[str] = None
    enable_research: bool = False
    research_provider: Optional[str] = None
    research_api_key: Optional[str] = None
    research_triggers: Optional[List[str]] = None
    research_verbs: Optional[List[str]] = None


def infer_meeting_type(title: str) -> Optional[str]:
    if not title:
        return None
    lowered = title.lower()
    if "standup" in lowered:
        return "Standup"
    if "retro" in lowered:
        return "Retro"
    if "planning" in lowered:
        return "Planning"
    if "brainstorm" in lowered:
        return "Brainstorm"
    if "sync" in lowered:
        return "Sync"
    return None


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_markdown(notes: Dict[str, Any], transcript: str, timeline: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(f"# {notes.get('title', 'Meeting Notes')}")
    lines.append("")
    lines.append(f"Date: {notes.get('date', '')}")
    attendees = notes.get("attendees", [])
    if attendees:
        lines.append(f"Attendees: {', '.join(attendees)}")
    lines.append("")

    def add_section(title: str, items: List[str]) -> None:
        lines.append(f"## {title}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")

    add_section("Summary", notes.get("summary", []))
    add_section("Decisions", notes.get("decisions", []))

    lines.append("## Action items")
    actions = notes.get("actions", [])
    if actions:
        for action in actions:
            owner = action.get("owner") or "Unassigned"
            task = action.get("task") or ""
            due = action.get("due") or ""
            suffix = f" (due {due})" if due else ""
            lines.append(f"- {owner}: {task}{suffix}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Top highlights")
    highlights = notes.get("highlights", [])
    if highlights:
        for item in highlights:
            lines.append(f"- [{item.get('ts','')}] {item.get('text','')}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Timeline summary")
    if timeline:
        for window in timeline:
            range_label = window.get("range", "")
            label = window.get("label", "")
            header = f"{range_label} - {label}".strip(" -")
            lines.append(f"**{header}**")
            for bullet in window.get("bullets", []) or []:
                lines.append(f"- {bullet}")
            lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    lines.append("## Research requests")
    research_requests = notes.get("research_requests", [])
    if research_requests:
        for item in research_requests:
            ts = item.get("ts", "")
            speaker = item.get("speaker", "")
            query = item.get("query", "")
            lines.append(f"- [{ts}] {speaker}: {query}".strip())
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Research results")
    research_results = notes.get("research_results", [])
    if research_results:
        for item in research_results:
            query = item.get("query", "")
            lines.append(f"**{query}**")
            for res in item.get("results", []) or []:
                title = res.get("title") or "Result"
                url = res.get("url") or ""
                snippet = res.get("snippet") or ""
                lines.append(f"- {title} {url}".strip())
                if snippet:
                    lines.append(f"  {snippet}")
            lines.append("")
    else:
        lines.append("- None")
        lines.append("")

    lines.append("## Transcript")
    lines.append("")
    lines.append(transcript)
    lines.append("")

    return "\n".join(lines)


def run_pipeline(
    config: PipelineConfig,
    logger: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[int, int, str, Optional[float]], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    def log(message: str) -> None:
        if logger:
            logger(message)

    load_dotenv()

    if config.openai_api_key:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
    if config.openai_model:
        os.environ["OPENAI_MODEL"] = config.openai_model
    if os.getenv("OPENAI_MODEL_FALLBACK") is None:
        os.environ["OPENAI_MODEL_FALLBACK"] = "gpt-5"
    if config.notion_token:
        os.environ["NOTION_TOKEN"] = config.notion_token
    if config.notion_database_id:
        os.environ["NOTION_DATABASE_ID"] = config.notion_database_id

    audio_dir = config.audio_dir.expanduser().resolve()
    if not audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Install ffmpeg and try again.")

    date = determine_date(config.date_override, audio_dir)
    date_str = format_date(date)

    base_dir = Path(__file__).resolve().parent
    transcripts_dir = base_dir / "transcripts" / date_str
    outputs_dir = base_dir / "outputs"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    device = "cpu"
    try:
        import torch

        if torch.cuda.is_available():
            device = "cuda"
    except Exception:
        device = "cpu"

    compute_type = "float16" if device == "cuda" else "int8"

    log("STATUS: Transcribing")
    log("Transcribing audio...")
    results = transcribe_directory(
        audio_dir,
        config.model,
        device,
        compute_type,
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )

    if not results:
        raise RuntimeError("No audio files found to transcribe or transcription cancelled.")

    attendees = sorted({r.speaker for r in results})

    for result in results:
        transcript_path = transcripts_dir / f"{result.speaker}.txt"
        write_text(transcript_path, result.text)

    segments = merge_segments(results)
    merged_text = merged_transcript_text(segments)
    write_text(transcripts_dir / "merged_transcript.txt", merged_text)
    save_segments_json(transcripts_dir / "segments.json", segments)
    normalized_transcript = normalize_trigger_text(merged_text)

    meeting_title = config.meeting_title if config.meeting_title not in ("", None) else None
    meeting_type = infer_meeting_type(meeting_title or "")

    notes: Dict[str, Any] = {
        "title": meeting_title or "Team Sync",
        "date": date_str,
        "attendees": attendees,
        "topics": [],
        "summary": [],
        "decisions": [],
        "actions": [],
        "highlights": [],
        "timeline": [],
        "key_discussion": [],
        "open_questions": [],
        "research_requests": [],
        "research_results": [],
    }

    model = os.getenv("OPENAI_MODEL", "gpt-5-pro")
    fallback_model = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-5")
    timeline: List[Dict[str, Any]] = []

    if config.summarise:
        try:
            log("STATUS: Summarising")
            notes.update(
                summarise_meeting(
                    transcript=normalized_transcript,
                    attendees=attendees,
                    date_str=date_str,
                    meeting_title=meeting_title,
                    model=model,
                    fallback_model=fallback_model,
                )
            )

            windows = group_segments_into_windows(segments, config.chunk_minutes)
            timeline = timeline_summary(windows, model=model, fallback_model=fallback_model)
            notes["timeline"] = timeline

            if not meeting_title:
                meeting_title = notes.get("title") or "Team Sync"
            notes["title"] = meeting_title
        except Exception as exc:
            log(f"Summarisation failed: {exc}")

    if not timeline and notes.get("timeline"):
        timeline = notes.get("timeline")

    if not meeting_title:
        meeting_title = notes.get("title") or "Team Sync"
    notes["title"] = meeting_title

    research_requests = extract_research_requests(
        normalized_transcript,
        triggers=config.research_triggers,
        verbs=config.research_verbs,
    )
    research_results = []
    if config.enable_research:
        log("STATUS: Researching")
        research_results = run_research(
            research_requests,
            provider=config.research_provider or "none",
            api_key=config.research_api_key,
        )

    notes["research_requests"] = [
        {"ts": r.ts, "speaker": r.speaker, "query": r.query} for r in research_requests
    ]
    notes["research_results"] = research_results

    notes_path = outputs_dir / f"{date_str}_meeting_notes.json"
    with notes_path.open("w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

    md_path = outputs_dir / f"{date_str}_meeting_notes.md"
    write_text(md_path, build_markdown(notes, merged_text, timeline))

    log(f"Saved notes to {md_path}")

    notion_url = ""
    if config.upload_notion and config.notion_enabled:
        token = os.getenv("NOTION_TOKEN")
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not token or not database_id:
            log("Notion credentials not set; skipping upload.")
        else:
            try:
                log("STATUS: Uploading to Notion")
                notion_url = upload_to_notion(
                    token=token,
                    database_id=database_id,
                    title=f"{date_str} - {meeting_title}",
                    date_str=date_str,
                    project=config.project,
                    meeting_type=meeting_type,
                    attendees=attendees,
                    actions_count=len(notes.get("actions", [])),
                    decisions_count=len(notes.get("decisions", [])),
                    status="Draft",
                    recording_url=config.recording_url,
                    summary=notes.get("summary", []),
                    decisions=notes.get("decisions", []),
                    actions=notes.get("actions", []),
                    highlights=notes.get("highlights", []),
                    timeline=timeline,
                    research_requests=notes.get("research_requests", []),
                    research_results=notes.get("research_results", []),
                    transcript=merged_text,
                )
                if notion_url:
                    log(f"Uploaded Notion page: {notion_url}")
                else:
                    log("Uploaded Notion page.")
            except Exception as exc:
                log(f"Notion upload failed: {exc}")

    log("STATUS: Done")
    return {
        "date": date_str,
        "notes_path": str(notes_path),
        "markdown_path": str(md_path),
        "notion_url": notion_url,
    }
