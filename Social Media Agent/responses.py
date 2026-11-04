"""
Shapes what the AI gets back.

Every answer is one JSON text block. Long answers drop items from the end so they fit the
response size limit, and say so; if not even one item fits, the answer explains why it is empty.
Section answers (profile, company, search) cut their longest sections instead and name them.
"""

import json
from typing import Any, Dict, List

from mcp.types import TextContent

from constants import MAX_RESPONSE_CHARS, MIN_CUT_SECTION_CHARS

CUT_MARKER = " …[cut to fit the response size limit]"


def to_text_content(payload: Any) -> List[TextContent]:
    """Wrap a Python value as a single JSON TextContent block for MCP responses."""
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


def fit_items(header: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return header plus as many items as fit MAX_RESPONSE_CHARS, marking any that were dropped."""
    kept = list(items)
    while True:
        response = {**header, "count": len(kept), "items": kept}
        if len(kept) < len(items):
            response["truncated"] = True
        if len(_serialized(response)) <= MAX_RESPONSE_CHARS:
            return response
        if len(kept) == 1:
            response.update(count=0, items=[])
            response["message"] = f"Each result is larger than the {MAX_RESPONSE_CHARS}-character response limit."
            return response
        kept.pop()


def fit_sections(header: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Return header plus a section answer that fits MAX_RESPONSE_CHARS.

    The longest section is cut in half until the answer fits, and the cut sections are named in
    `truncated_sections`, so the AI can ask again for fewer sections. Links are dropped only if the
    text alone cannot make it fit.
    """
    response = {**header, **result, "sections": dict(result["sections"])}
    cut: List[str] = []
    while len(_serialized(response)) > MAX_RESPONSE_CHARS:
        name = max(response["sections"], key=lambda section: len(response["sections"][section]), default=None)
        if name is None or len(response["sections"][name]) <= MIN_CUT_SECTION_CHARS:
            break
        text = response["sections"][name]
        response["sections"][name] = text[: len(text) // 2].rstrip() + CUT_MARKER
        if name not in cut:
            cut.append(name)
    if cut:
        response["truncated_sections"] = cut
    if len(_serialized(response)) > MAX_RESPONSE_CHARS and "references" in response:
        del response["references"]
        response["references_dropped"] = True
    return response


def _serialized(response: Dict[str, Any]) -> str:
    return json.dumps(response, ensure_ascii=False)
