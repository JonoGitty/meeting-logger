# Meeting Logger

Plaud-style meeting notes from Craig recordings. Transcribe locally with faster-whisper, summarise with OpenAI, and upload to Notion.

## Part 1: Craig setup (record everyone)
1) Invite Craig to your Discord server.
2) Create a text channel for recordings (optional but recommended).
3) Start recording:
   - Join the voice channel
   - In the text channel: `:craig:, join`
   - If needed: `:craig:, record`
4) Stop recording:
   - `:craig:, leave` (or `:craig:, stop` then leave)
5) Download the recording package (prefer multi-track / per-speaker output).
6) Place files in:
   `meeting_logger/audio/YYYY-MM-DD/raw_audio/`

## Part 2: Local pipeline

### Windows setup
1) Install Python 3.10+.
2) Install FFmpeg (required). Easiest option:
   - `winget install Gyan.FFmpeg`
   - Restart your terminal after install.
3) Create and activate a virtual environment:
   - `python -m venv venv`
   - `venv\Scripts\activate`
4) Install dependencies:
   - `pip install --upgrade pip`
   - `pip install -r requirements.txt`
5) Copy `.env.example` to `.env` and set keys.

### Windows quick install + GUI
Run these from the `meeting_logger` folder:

```
install.bat
launch.bat
```

`launch.bat` will open the GUI and will run the installer automatically if needed.

### Linux/macOS setup
1) Install FFmpeg and Python:
   - `sudo apt install ffmpeg python3 python3-venv -y`
2) Create and activate a virtual environment:
   - `python3 -m venv venv`
   - `source venv/bin/activate`
3) Install dependencies:
   - `pip install --upgrade pip`
   - `pip install -r requirements.txt`
4) Copy `.env.example` to `.env` and set keys.

### Notion setup (one time)
1) Create a Notion database named `Meeting Logs`.
2) Add these properties (recommended):
   - Name (Title)
   - Date (Date)
   - Project (Select)
   - Type (Select)
   - Attendees (Multi-select)
   - Actions (Number)
   - Decisions (Number)
   - Status (Select)
   - Recording (URL)
3) Create an internal integration and copy the token.
4) Share the database with the integration.
5) Put the token and database ID in `.env`.

## Usage

Example command:

```
python cli.py --audio_dir "./audio/2026-01-24/raw_audio" --project "AI-Orch" --chunk_minutes 5 --upload_notion
```

GUI:
- Run `launch.bat` on Windows.
- All CLI options are exposed in the Settings tab.

Options:
- `--meeting` provide a fixed title (otherwise auto-generated).
- `--date` override date detection (YYYY-MM-DD).
- `--model` whisper model: tiny/small/medium.
- `--recording_url` attach a link in Notion.
- `--no_summarise` skip OpenAI summarisation.
- `--no_notion` skip Notion upload.

Outputs:
- `transcripts/<date>/Speaker.txt`
- `transcripts/<date>/merged_transcript.txt`
- `transcripts/<date>/segments.json`
- `outputs/<date>_meeting_notes.json`
- `outputs/<date>_meeting_notes.md`

## Notes
- Multi-track recordings are strongly recommended for clean speaker attribution.
- If Notion upload fails, local outputs are still saved.
- The timeline summary uses 5-minute blocks by default.
