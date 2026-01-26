from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _get_openai_client():
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("openai package is not installed") from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def _call_openai_json(model: str, system: str, user: str) -> Dict[str, Any]:
    client = _get_openai_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Empty response from OpenAI")
    return json.loads(content)


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def summarise_meeting(
    transcript: str,
    attendees: List[str],
    date_str: str,
    meeting_title: Optional[str],
    model: str,
) -> Dict[str, Any]:
    title_hint = meeting_title or ""

    system = (
        "You produce accurate meeting notes from transcripts. "
        "Only use content that appears in the transcript. "
        "Do not invent decisions or actions. "
        "Return strict JSON only."
    )

    user = (
        "Create structured meeting notes from this transcript.\n\n"
        f"Date: {date_str}\n"
        f"Attendees (from file names): {', '.join(attendees) if attendees else 'Unknown'}\n"
        f"Meeting title hint (may be blank): {title_hint}\n\n"
        "JSON schema to output:\n"
        "{\n"
        "  \"title\": string,\n"
        "  \"topics\": [string],\n"
        "  \"summary\": [string],\n"
        "  \"decisions\": [string],\n"
        "  \"actions\": [{\"owner\": string|null, \"task\": string, \"due\": string|null}],\n"
        "  \"highlights\": [{\"ts\": string, \"text\": string}],\n"
        "  \"key_discussion\": [string],\n"
        "  \"open_questions\": [string]\n"
        "}\n\n"
        "Rules:\n"
        "- If meeting title hint is blank, generate a short 3-7 word title based on the dominant theme.\n"
        "- If title hint is provided, use it verbatim.\n"
        "- Highlights must be 5-8 items, each with timestamp like mm:ss or hh:mm:ss and one sentence.\n"
        "- Actions must only include tasks clearly stated in transcript.\n"
        "- Decisions should be explicit.\n"
        "- Keep summary and key discussion concise.\n\n"
        "Transcript:\n"
        f"{transcript}"
    )

    data = _call_openai_json(model=model, system=system, user=user)

    return {
        "title": data.get("title") or (meeting_title or "Team Sync"),
        "topics": _safe_list(data.get("topics")),
        "summary": _safe_list(data.get("summary")),
        "decisions": _safe_list(data.get("decisions")),
        "actions": _safe_list(data.get("actions")),
        "highlights": _safe_list(data.get("highlights")),
        "key_discussion": _safe_list(data.get("key_discussion")),
        "open_questions": _safe_list(data.get("open_questions")),
    }


def timeline_summary(
    windows: List[Dict[str, Any]],
    model: str,
) -> List[Dict[str, Any]]:
    if not windows:
        return []

    system = (
        "You generate timeline summaries for meeting transcripts. "
        "Only use the provided text. Return strict JSON only."
    )

    window_payload = []
    for win in windows:
        text_lines = []
        for seg in win.get("segments", []):
            speaker = seg.get("speaker", "Speaker")
            text = seg.get("text", "").strip()
            if text:
                text_lines.append(f"{speaker}: {text}")
        window_payload.append({
            "range": win.get("range"),
            "text": "\n".join(text_lines),
        })

    user = (
        "Summarise each time window into a short chapter label and 3-6 bullets.\n\n"
        "Return JSON:\n"
        "{\n"
        "  \"timeline\": [\n"
        "    {\"range\": string, \"label\": string, \"bullets\": [string]}\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Keep labels short and descriptive.\n"
        "- Bullets must be grounded in the text.\n\n"
        f"Windows:\n{json.dumps(window_payload, ensure_ascii=False)}"
    )

    data = _call_openai_json(model=model, system=system, user=user)
    return _safe_list(data.get("timeline"))
