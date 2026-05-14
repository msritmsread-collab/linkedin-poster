"""
LinkedIn Content Generator
Generates 3 distinct 250-word LinkedIn post options using Claude,
writing in the voice of MS. READ's seasoned HR Manager.
"""

import json
import os
import re
from typing import List, Optional

import anthropic

from config.brand import COMPANY, HR_PERSONA, CONTENT_STRATEGY


_SYSTEM_PROMPT = f"""You are {HR_PERSONA['role']} at {HR_PERSONA['company']}.

About you:
{HR_PERSONA['personality']}

Your expertise covers: {', '.join(HR_PERSONA['expertise'])}.

About the company:
{COMPANY['about']}

LinkedIn objective:
{CONTENT_STRATEGY['objective']}

Voice & tone: {HR_PERSONA['voice']['tone']}

Avoid: {', '.join(HR_PERSONA['voice']['avoid'])}

IMPORTANT RULES:
- Every post must be EXACTLY around 250 words (240-260 words)
- Write in first-person as the HR Manager
- Posts must feel authentic, not like marketing copy
- Each post must end with 3-5 relevant hashtags from this pool:
  {' '.join(CONTENT_STRATEGY['hashtags'])}
- Always include a clear CTA at the end (before hashtags)
- Do NOT include the word count or label in the output
- Do NOT use em-dashes excessively; write naturally
- Malaysia context: write for a Malaysian professional audience on LinkedIn
"""


def _load_reference_posts() -> List[dict]:
    """Load saved reference posts from DB settings."""
    try:
        from backend.database import get_setting
        raw = get_setting("reference_posts") or "[]"
        refs = json.loads(raw)
        return [r for r in refs if r.get("text", "").strip()]
    except Exception:
        return []


def _build_reference_block(refs: List[dict]) -> str:
    if not refs:
        return ""
    lines = ["\nREFERENCE EXAMPLES — study these real MS. READ LinkedIn posts for tone, structure, and voice. Mirror this style:"]
    for i, ref in enumerate(refs[:6], 1):  # cap at 6 references
        label = ref.get("label") or f"Example {i}"
        text = ref.get("text", "").strip()
        lines.append(f"\n--- {label} ---\n{text}")
    lines.append("\n--- END OF REFERENCES ---")
    lines.append("Use these as your style guide. Do NOT copy or paraphrase them — generate original content that matches this voice.\n")
    return "\n".join(lines)


def _build_user_prompt(topic: Optional[str], blocked_keywords: List[str]) -> str:
    topic_line = f"Main topic (optional guidance): {topic}" if topic else "No specific topic provided — choose the most timely and relevant angle."

    blocked_line = ""
    if blocked_keywords:
        blocked_line = f"\nAVOID these recently rejected topics/angles (blocked for 6 months): {'; '.join(blocked_keywords[:10])}"

    refs = _load_reference_posts()
    reference_block = _build_reference_block(refs)

    angles = CONTENT_STRATEGY["content_angles"]

    return f"""Generate exactly 3 LinkedIn posts for MS. READ's company page.

{topic_line}
{blocked_line}
{reference_block}
Each post must use a DIFFERENT angle as described below:

Option A — {angles[0]['name']}:
{angles[0]['description']}

Option B — {angles[1]['name']}:
{angles[1]['description']}

Option C — {angles[2]['name']}:
{angles[2]['description']}

Return your response as a valid JSON object in this exact format:
{{
  "options": [
    {{
      "label": "A",
      "angle_name": "{angles[0]['name']}",
      "content": "<full 250-word post text including CTA and hashtags>"
    }},
    {{
      "label": "B",
      "angle_name": "{angles[1]['name']}",
      "content": "<full 250-word post text including CTA and hashtags>"
    }},
    {{
      "label": "C",
      "angle_name": "{angles[2]['name']}",
      "content": "<full 250-word post text including CTA and hashtags>"
    }}
  ]
}}

Only return the JSON object — no markdown fences, no extra text.
"""


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """Call Claude API directly via the anthropic SDK."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def generate_options(topic: Optional[str], blocked_keywords: Optional[List[str]] = None) -> List[dict]:
    """
    Call Claude and return a list of 3 option dicts:
    [{"label": "A", "angle_name": ..., "content": ...}, ...]
    """
    prompt = _build_user_prompt(topic, blocked_keywords or [])
    raw = _call_claude(_SYSTEM_PROMPT, prompt)

    # Strip any accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        data = json.loads(raw)
        options = data.get("options", [])
        if len(options) != 3:
            raise ValueError(f"Expected 3 options, got {len(options)}")
        # Validate required fields
        for opt in options:
            assert opt.get("label") in ("A", "B", "C"), "Invalid label"
            assert opt.get("angle_name"), "Missing angle_name"
            assert opt.get("content"), "Missing content"
        return options
    except (json.JSONDecodeError, ValueError, AssertionError) as e:
        # Fallback: attempt to extract JSON from within the response
        match = re.search(r'\{.*"options"\s*:.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data.get("options", [])
        raise RuntimeError(f"Content generation failed to parse: {e}\nRaw: {raw[:500]}")
