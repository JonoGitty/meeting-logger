# Meeting Logger

Local-first Discord meeting logger that transcribes Craig multi-track recordings, generates Plaud-style notes, and uploads to Notion.

Project lives in `meeting_logger/`.

## Quick start (Windows)
1) Run `meeting_logger\install.bat`
2) Run `meeting_logger\launch.bat`

## Quick start (CLI)
```
cd meeting_logger
python cli.py --audio_dir "./audio/YYYY-MM-DD/raw_audio" --project "AI-Orch" --chunk_minutes 5 --upload_notion
```

## Security
- Secrets live in `.env` (ignored by git)
- Audio, transcripts, outputs, and logs are ignored by git

See `meeting_logger/README.md` for full setup details.
