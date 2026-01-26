from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from dotenv import load_dotenv

from pipeline import PipelineConfig, run_pipeline

console = Console()
load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Plaud-style meeting notes from Craig recordings.")
    parser.add_argument("--audio_dir", required=True, help="Folder containing per-speaker audio files")
    parser.add_argument("--project", default=None, help="Project name for Notion property")
    parser.add_argument("--meeting", default=None, help="Meeting title (leave blank to auto-generate)")
    parser.add_argument("--date", default=None, help="Meeting date YYYY-MM-DD")
    parser.add_argument("--chunk_minutes", type=int, default=5, help="Timeline chunk size in minutes")
    parser.add_argument("--model", default="small", help="Whisper model size (tiny/small/medium)")
    parser.add_argument("--recording_url", default=None, help="Recording URL for Notion")
    parser.add_argument("--upload_notion", action="store_true", help="Upload results to Notion")
    parser.add_argument("--no_summarise", action="store_true", help="Skip OpenAI summarisation")
    parser.add_argument("--no_notion", action="store_true", help="Skip Notion upload")

    args = parser.parse_args()

    config = PipelineConfig(
        audio_dir=Path(args.audio_dir),
        project=args.project,
        meeting_title=args.meeting,
        date_override=args.date,
        chunk_minutes=args.chunk_minutes,
        model=args.model,
        recording_url=args.recording_url,
        upload_notion=args.upload_notion,
        summarise=not args.no_summarise,
        notion_enabled=not args.no_notion,
    )

    try:
        run_pipeline(config, logger=console.print)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")


if __name__ == "__main__":
    main()
