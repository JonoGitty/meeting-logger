from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

DEFAULT_TRIGGERS = [
    "craig",
    "quag",
    "crag",
    "graig",
    "craig.",
]

DEFAULT_VERBS = [
    "google",
    "googl",
    "goodgle",
    "search",
    "research",
    "find",
    "lookup",
    "look up",
    "check",
]


@dataclass
class ResearchRequest:
    ts: str
    speaker: str
    query: str
    raw_line: str


def normalize_trigger_text(text: str) -> str:
    replacements = {
        "quag": "craig",
        "crag": "craig",
        "graig": "craig",
        "craiq": "craig",
        "creg": "craig",
    }
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in replacements.keys()) + r")\b", re.IGNORECASE)

    def repl(match: re.Match) -> str:
        key = match.group(1).lower()
        return replacements.get(key, match.group(1))

    return pattern.sub(repl, text)


def extract_research_requests(
    transcript: str,
    triggers: Optional[List[str]] = None,
    verbs: Optional[List[str]] = None,
) -> List[ResearchRequest]:
    if not transcript:
        return []

    triggers = triggers or DEFAULT_TRIGGERS
    verbs = verbs or DEFAULT_VERBS

    trigger_pattern = "|".join(re.escape(t) for t in triggers)
    verb_pattern = "|".join(re.escape(v) for v in verbs)
    command_re = re.compile(
        rf"\b(?P<trigger>{trigger_pattern})\b\s*[,:\-]?\s*(?P<verb>{verb_pattern})\s+(?P<query>.+)$",
        re.IGNORECASE,
    )

    results: List[ResearchRequest] = []
    line_re = re.compile(r"^\[(?P<ts>\d{2}:\d{2}:\d{2})\]\s+(?P<speaker>[^:]+):\s+(?P<text>.+)$")

    for raw_line in transcript.splitlines():
        match = line_re.match(raw_line.strip())
        if not match:
            continue
        ts = match.group("ts")
        speaker = match.group("speaker").strip()
        text = normalize_trigger_text(match.group("text"))
        cmd_match = command_re.search(text)
        if not cmd_match:
            continue
        query = cmd_match.group("query").strip()
        if not query:
            continue
        results.append(ResearchRequest(ts=ts, speaker=speaker, query=query, raw_line=raw_line))

    return results


def tavily_search(query: str, api_key: str, max_results: int = 5) -> List[Dict[str, Any]]:
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "include_images": False,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", []):
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content") or item.get("snippet"),
            }
        )
    return results


def run_research(
    requests_list: List[ResearchRequest],
    provider: str,
    api_key: Optional[str],
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    if not requests_list:
        return []

    provider = (provider or "none").lower()
    results: List[Dict[str, Any]] = []

    if provider == "tavily":
        if not api_key:
            return []
        for item in requests_list:
            items = tavily_search(item.query, api_key=api_key, max_results=max_results)
            results.append(
                {
                    "ts": item.ts,
                    "speaker": item.speaker,
                    "query": item.query,
                    "results": items,
                }
            )
        return results

    return []
