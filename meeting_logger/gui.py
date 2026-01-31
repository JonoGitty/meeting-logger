from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk, messagebox

from pipeline import PipelineConfig, run_pipeline
from utils.date_utils import determine_date, format_date


class MeetingLoggerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Meeting Logger")
        self.root.geometry("920x720")

        self.base_dir = Path(__file__).resolve().parent
        self.env_path = self.base_dir / ".env"

        self._build_ui()
        self._load_env()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.main_frame = ttk.Frame(notebook)
        self.settings_frame = ttk.Frame(notebook)
        self.log_frame = ttk.Frame(notebook)

        notebook.add(self.main_frame, text="Run")
        notebook.add(self.settings_frame, text="Settings")
        notebook.add(self.log_frame, text="Log")

        self._build_main_tab()
        self._build_settings_tab()
        self._build_log_tab()

    def _build_main_tab(self) -> None:
        frame = self.main_frame

        audio_frame = ttk.LabelFrame(frame, text="Audio + Meeting")
        audio_frame.pack(fill="x", padx=10, pady=10)

        self.audio_dir_var = tk.StringVar()
        self.meeting_title_var = tk.StringVar()
        self.project_var = tk.StringVar()
        self.date_override_var = tk.StringVar()
        self.recording_url_var = tk.StringVar()
        self.auto_date_var = tk.StringVar(value="Auto date: ")

        ttk.Label(audio_frame, text="Audio folder").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        audio_entry = ttk.Entry(audio_frame, textvariable=self.audio_dir_var, width=60)
        audio_entry.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        ttk.Button(audio_frame, text="Browse", command=self._browse_audio).grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(audio_frame, textvariable=self.auto_date_var).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(audio_frame, text="Meeting title (blank = auto)").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(audio_frame, textvariable=self.meeting_title_var, width=60).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(audio_frame, text="Project").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(audio_frame, textvariable=self.project_var, width=40).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(audio_frame, text="Date override (YYYY-MM-DD)").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(audio_frame, textvariable=self.date_override_var, width=20).grid(row=4, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(audio_frame, text="Recording URL").grid(row=5, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(audio_frame, textvariable=self.recording_url_var, width=60).grid(row=5, column=1, sticky="w", padx=6, pady=6)

        processing_frame = ttk.LabelFrame(frame, text="Processing")
        processing_frame.pack(fill="x", padx=10, pady=10)

        self.model_var = tk.StringVar(value="small")
        self.chunk_minutes_var = tk.IntVar(value=5)
        self.summarise_var = tk.BooleanVar(value=True)
        self.upload_notion_var = tk.BooleanVar(value=True)
        self.enable_research_var = tk.BooleanVar(value=False)

        ttk.Label(processing_frame, text="Whisper model").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Combobox(processing_frame, textvariable=self.model_var, values=["tiny", "small", "medium"], width=10, state="readonly").grid(
            row=0, column=1, sticky="w", padx=6, pady=6
        )

        ttk.Label(processing_frame, text="Timeline chunk (minutes)").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Spinbox(processing_frame, from_=1, to=30, textvariable=self.chunk_minutes_var, width=5).grid(
            row=0, column=3, sticky="w", padx=6, pady=6
        )

        ttk.Checkbutton(processing_frame, text="Generate summaries (OpenAI)", variable=self.summarise_var).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6, pady=6
        )
        ttk.Checkbutton(processing_frame, text="Upload to Notion", variable=self.upload_notion_var).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=6, pady=6
        )
        ttk.Checkbutton(processing_frame, text="Enable research requests", variable=self.enable_research_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6
        )

        control_frame = ttk.Frame(frame)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.run_button = ttk.Button(control_frame, text="Run", command=self._run_pipeline)
        self.run_button.pack(side="left", padx=6)

        ttk.Button(control_frame, text="Open outputs folder", command=self._open_outputs).pack(side="left", padx=6)

        status_frame = ttk.Frame(frame)
        status_frame.pack(fill="x", padx=10, pady=10)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left", padx=6)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=400)
        self.progress.pack(side="left", padx=6, fill="x", expand=True)
        self.cancel_button = ttk.Button(status_frame, text="Cancel", command=self._cancel_run, state="disabled")
        self.cancel_button.pack(side="left", padx=6)

    def _build_settings_tab(self) -> None:
        frame = self.settings_frame

        creds_frame = ttk.LabelFrame(frame, text="Credentials")
        creds_frame.pack(fill="x", padx=10, pady=10)

        self.openai_key_var = tk.StringVar()
        self.openai_model_var = tk.StringVar(value="gpt-5-pro")
        self.openai_fallback_var = tk.StringVar(value="gpt-5")
        self.notion_token_var = tk.StringVar()
        self.notion_db_var = tk.StringVar()
        self.research_provider_var = tk.StringVar(value="none")
        self.research_api_key_var = tk.StringVar()
        self.research_triggers_var = tk.StringVar(value="craig,quag,crag,graig")
        self.research_verbs_var = tk.StringVar(value="google,search,research,find,lookup,look up,check")

        ttk.Label(creds_frame, text="OpenAI API key").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_frame, textvariable=self.openai_key_var, width=60, show="*").grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(creds_frame, text="OpenAI model").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_frame, textvariable=self.openai_model_var, width=20).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(creds_frame, text="OpenAI fallback model").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_frame, textvariable=self.openai_fallback_var, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(creds_frame, text="Notion token").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_frame, textvariable=self.notion_token_var, width=60, show="*").grid(row=3, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(creds_frame, text="Notion database ID").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(creds_frame, textvariable=self.notion_db_var, width=60).grid(row=4, column=1, sticky="w", padx=6, pady=6)

        research_frame = ttk.LabelFrame(frame, text="Research")
        research_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(research_frame, text="Provider").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Combobox(research_frame, textvariable=self.research_provider_var, values=["none", "tavily"], width=12, state="readonly").grid(
            row=0, column=1, sticky="w", padx=6, pady=6
        )

        ttk.Label(research_frame, text="Tavily API key").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(research_frame, textvariable=self.research_api_key_var, width=60, show="*").grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(research_frame, text="Trigger words (CSV)").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(research_frame, textvariable=self.research_triggers_var, width=60).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(research_frame, text="Verbs (CSV)").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(research_frame, textvariable=self.research_verbs_var, width=60).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        action_frame = ttk.Frame(frame)
        action_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(action_frame, text="Load .env", command=self._load_env).pack(side="left", padx=6)
        ttk.Button(action_frame, text="Save .env", command=self._save_env).pack(side="left", padx=6)

        note = ttk.Label(frame, text="Settings are saved to .env in the meeting_logger folder.")
        note.pack(fill="x", padx=10)

    def _build_log_tab(self) -> None:
        self.log_text = tk.Text(self.log_frame, height=20, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log(self, message: str) -> None:
        if message.startswith("STATUS:"):
            status = message.split("STATUS:", 1)[1].strip()
            self._set_status(status)
        self.root.after(0, self._append_log, message)

    def _set_status(self, status: str) -> None:
        def apply() -> None:
            self.status_var.set(status)
        self.root.after(0, apply)

    def _browse_audio(self) -> None:
        folder = filedialog.askdirectory(title="Select audio folder")
        if folder:
            self.audio_dir_var.set(folder)
            self._update_auto_date()

    def _update_auto_date(self) -> None:
        audio_dir = Path(self.audio_dir_var.get()).expanduser()
        if audio_dir.exists():
            date = determine_date(None, audio_dir)
            self.auto_date_var.set(f"Auto date: {format_date(date)}")
        else:
            self.auto_date_var.set("Auto date: ")

    def _open_outputs(self) -> None:
        outputs_path = self.base_dir / "outputs"
        outputs_path.mkdir(exist_ok=True)
        os.startfile(outputs_path)  # type: ignore[attr-defined]

    def _load_env(self) -> None:
        if not self.env_path.exists():
            return
        data = {}
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()

        self.openai_key_var.set(data.get("OPENAI_API_KEY", ""))
        self.openai_model_var.set(data.get("OPENAI_MODEL", "gpt-5-pro"))
        self.openai_fallback_var.set(data.get("OPENAI_MODEL_FALLBACK", "gpt-5"))
        self.notion_token_var.set(data.get("NOTION_TOKEN", ""))
        self.notion_db_var.set(data.get("NOTION_DATABASE_ID", ""))
        self.research_provider_var.set(data.get("RESEARCH_PROVIDER", "none"))
        self.research_api_key_var.set(data.get("TAVILY_API_KEY", ""))
        self.research_triggers_var.set(data.get("RESEARCH_TRIGGERS", "craig,quag,crag,graig"))
        self.research_verbs_var.set(data.get("RESEARCH_VERBS", "google,search,research,find,lookup,look up,check"))

    def _save_env(self) -> None:
        lines = [
            f"OPENAI_API_KEY={self.openai_key_var.get().strip()}",
            f"OPENAI_MODEL={self.openai_model_var.get().strip() or 'gpt-5-pro'}",
            f"OPENAI_MODEL_FALLBACK={self.openai_fallback_var.get().strip() or 'gpt-5'}",
            f"NOTION_TOKEN={self.notion_token_var.get().strip()}",
            f"NOTION_DATABASE_ID={self.notion_db_var.get().strip()}",
            f"RESEARCH_PROVIDER={self.research_provider_var.get().strip() or 'none'}",
            f"TAVILY_API_KEY={self.research_api_key_var.get().strip()}",
            f"RESEARCH_TRIGGERS={self.research_triggers_var.get().strip()}",
            f"RESEARCH_VERBS={self.research_verbs_var.get().strip()}",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        messagebox.showinfo("Saved", ".env saved successfully.")

    def _run_pipeline(self) -> None:
        audio_dir = self.audio_dir_var.get().strip()
        if not audio_dir:
            messagebox.showerror("Missing audio folder", "Please select an audio folder.")
            return

        triggers = [t.strip() for t in self.research_triggers_var.get().split(",") if t.strip()]
        verbs = [v.strip() for v in self.research_verbs_var.get().split(",") if v.strip()]

        config = PipelineConfig(
            audio_dir=Path(audio_dir),
            project=self.project_var.get().strip() or None,
            meeting_title=self.meeting_title_var.get().strip() or None,
            date_override=self.date_override_var.get().strip() or None,
            chunk_minutes=int(self.chunk_minutes_var.get()),
            model=self.model_var.get().strip() or "small",
            recording_url=self.recording_url_var.get().strip() or None,
            upload_notion=self.upload_notion_var.get(),
            summarise=self.summarise_var.get(),
            notion_enabled=True,
            openai_api_key=self.openai_key_var.get().strip() or None,
            openai_model=self.openai_model_var.get().strip() or None,
            notion_token=self.notion_token_var.get().strip() or None,
            notion_database_id=self.notion_db_var.get().strip() or None,
            enable_research=self.enable_research_var.get(),
            research_provider=self.research_provider_var.get().strip() or None,
            research_api_key=self.research_api_key_var.get().strip() or None,
            research_triggers=triggers or None,
            research_verbs=verbs or None,
        )

        self.run_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self._set_status("Running")
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(10)
        self._log("Starting pipeline...")

        start_time = time.time()
        self._cancel_flag = threading.Event()
        durations: list[float] = []

        def progress_cb(current: int, total: int, speaker: str, duration: float | None) -> None:
            def apply() -> None:
                if duration:
                    durations.append(duration)
                if durations:
                    avg_seconds = (time.time() - start_time) / max(1, len(durations))
                    remaining = max(0, total - current)
                    eta_min = int((avg_seconds * remaining) / 60)
                    eta_text = f"~{eta_min} min left" if eta_min >= 1 else "<1 min left"
                else:
                    eta_text = ""
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=total, value=current)
                self.status_var.set(f"Transcribing {speaker} ({current}/{total}) {eta_text}".strip())
            self.root.after(0, apply)

        def worker() -> None:
            try:
                result = run_pipeline(
                    config,
                    logger=self._log,
                    progress_cb=progress_cb,
                    cancel_cb=self._cancel_flag.is_set,
                )
                self._log(f"Done. Notes saved to {result.get('markdown_path')}")
                if result.get("notion_url"):
                    self._log(f"Notion page: {result.get('notion_url')}")
            except Exception as exc:
                self._log(f"Error: {exc}")
            finally:
                def finish() -> None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=100, value=100)
                    self.status_var.set("Idle")
                    self.run_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_run(self) -> None:
        if hasattr(self, "_cancel_flag"):
            self._cancel_flag.set()
            self._log("Cancel requested. Finishing current file...")
            self._set_status("Cancelling")


if __name__ == "__main__":
    app_root = tk.Tk()
    MeetingLoggerApp(app_root)
    app_root.mainloop()
