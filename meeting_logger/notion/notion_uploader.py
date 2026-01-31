from __future__ import annotations

from typing import Any, Dict, List, Optional

from notion_client import Client

from utils.chunking import chunk_text


def _rich_text(text: str, bold: bool = False) -> List[Dict[str, Any]]:
    if text is None:
        text = ""
    return [
        {
            "type": "text",
            "text": {"content": text},
            "annotations": {"bold": bold},
        }
    ]


def _heading(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _rich_text(text)},
    }


def _paragraph(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _bulleted(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _todo(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _rich_text(text), "checked": False},
    }


def _callout(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": _rich_text(text)},
    }


def _toggle(title: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {"rich_text": _rich_text(title), "children": children},
    }


def _chunk_blocks(blocks: List[Dict[str, Any]], size: int = 50) -> List[List[Dict[str, Any]]]:
    return [blocks[i : i + size] for i in range(0, len(blocks), size)]


def _filter_properties(db_props: Dict[str, Any], desired: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in desired.items() if key in db_props}


def upload_to_notion(
    token: str,
    database_id: str,
    title: str,
    date_str: str,
    project: Optional[str],
    meeting_type: Optional[str],
    attendees: List[str],
    actions_count: int,
    decisions_count: int,
    status: str,
    recording_url: Optional[str],
    summary: List[str],
    decisions: List[str],
    actions: List[Dict[str, Any]],
    highlights: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    research_requests: List[Dict[str, Any]],
    research_results: List[Dict[str, Any]],
    transcript: str,
) -> str:
    notion = Client(auth=token)
    db = notion.databases.retrieve(database_id=database_id)
    db_props = db.get("properties", {})

    title_prop = "Name"
    for prop_name, prop in db_props.items():
        if prop.get("type") == "title":
            title_prop = prop_name
            break

    properties: Dict[str, Any] = {
        "Date": {"date": {"start": date_str}},
        "Status": {"select": {"name": status}},
        "Actions": {"number": actions_count},
        "Decisions": {"number": decisions_count},
        "Attendees": {"multi_select": [{"name": name} for name in attendees]},
    }
    properties[title_prop] = {"title": [{"text": {"content": title}}]}

    if project:
        properties["Project"] = {"select": {"name": project}}
    if meeting_type:
        properties["Type"] = {"select": {"name": meeting_type}}
    if recording_url:
        properties["Recording"] = {"url": recording_url}

    properties = _filter_properties(db_props, properties)

    page = notion.pages.create(
        parent={"database_id": database_id},
        properties=properties,
    )
    page_id = page["id"]

    blocks: List[Dict[str, Any]] = []
    blocks.append(_callout("Auto-generated meeting notes. Transcript stored below."))

    blocks.append(_heading("Summary"))
    if summary:
        blocks.extend([_bulleted(item) for item in summary])
    else:
        blocks.append(_bulleted("No summary generated."))

    blocks.append(_heading("Decisions"))
    if decisions:
        blocks.extend([_bulleted(item) for item in decisions])
    else:
        blocks.append(_bulleted("No explicit decisions recorded."))

    blocks.append(_heading("Action items"))
    if actions:
        for item in actions:
            owner = item.get("owner") or "Unassigned"
            task = item.get("task") or ""
            due = item.get("due") or ""
            suffix = f" (due {due})" if due else ""
            blocks.append(_todo(f"{owner} - {task}{suffix}".strip()))
    else:
        blocks.append(_todo("No action items captured."))

    blocks.append(_heading("Top highlights"))
    if highlights:
        for item in highlights:
            ts = item.get("ts") or ""
            text = item.get("text") or ""
            blocks.append(_bulleted(f"[{ts}] {text}".strip()))
    else:
        blocks.append(_bulleted("No highlights generated."))

    blocks.append(_heading("Timeline summary"))
    if timeline:
        for window in timeline:
            range_label = window.get("range", "")
            label = window.get("label", "")
            title = f"{range_label} - {label}".strip(" -")
            blocks.append(_paragraph(title))
            for bullet in window.get("bullets", []) or []:
                blocks.append(_bulleted(bullet))
    else:
        blocks.append(_bulleted("No timeline summary generated."))

    blocks.append(_heading("Research requests"))
    if research_requests:
        for item in research_requests:
            ts = item.get("ts", "")
            speaker = item.get("speaker", "")
            query = item.get("query", "")
            blocks.append(_bulleted(f"[{ts}] {speaker}: {query}".strip()))
    else:
        blocks.append(_bulleted("No research requests recorded."))

    blocks.append(_heading("Research results"))
    if research_results:
        for item in research_results:
            query = item.get("query", "")
            blocks.append(_paragraph(query))
            for res in item.get("results", []) or []:
                title = res.get("title") or "Result"
                url = res.get("url") or ""
                snippet = res.get("snippet") or ""
                line = f"{title} {url}".strip()
                blocks.append(_bulleted(line))
                if snippet:
                    blocks.append(_paragraph(snippet))
    else:
        blocks.append(_bulleted("No research results available."))

    blocks.append(_heading("Transcript"))
    transcript_children = []
    for part in chunk_text(transcript, max_chars=1800):
        transcript_children.append(_paragraph(part))
    blocks.append(_toggle("Full transcript (speaker-labelled)", transcript_children))

    for chunk in _chunk_blocks(blocks, size=50):
        notion.blocks.children.append(block_id=page_id, children=chunk)

    return page.get("url", "")
