"""LLM structuring of Nemotron Parse blocks (with 1 validation retry + vision fallback)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from config import settings
from services.nvidia_client import chat_completion, compress_image_for_api, file_sha256, image_to_data_url
from services.parse import NO_THINKING, ParsedBlock, message_text

STRUCTURE_SYSTEM_PROMPT = """You extract data from ONE diabetes lab report or prescription. You receive text blocks, each with an id.
Return ONLY a JSON object with this shape:
{"kind":"lab"|"rx"|"unknown","source_org":string|null,"doc_date":string|null,"doc_date_block":string|null,
 "observations":[{"label":string,"value":string,"unit":string|null,"block_id":string,"uncertain":boolean,"note":string|null}],
 "medications":[{"name":string,"strength":string|null,"frequency":string|null,"block_id":string,"uncertain":boolean,"note":string|null}]}
Rules:
- Copy values exactly as written. Do not convert units, do not correct spelling, do not compute anything.
- Every item must have the block_id of the block it was read from. If you cannot point to a block, leave the item out.
- If any character of a value, unit, dose or date is unclear, smudged or ambiguous, set "uncertain": true and explain in "note". Never guess.
- Do not add medical interpretation, diagnosis, or advice. Extract only.
- Only include an item that is actually written on this page. Never add a test or medicine from these instructions or from memory.
- "label" is the name of the thing that was measured, exactly as written just before its number. It is never a diagnosis and never a whole line.
- "value" is only the number as written. Put the unit in "unit".
- A doctor's handwritten note or prescription with advice or medicines has kind "rx".
- Include only these tests if present: HbA1c, fasting / post-meal / random glucose (RBS), creatinine, eGFR, urine albumin-creatinine ratio, total cholesterol, LDL, HDL, triglycerides.
- Include every medicine, drink, fluid or supplement that is prescribed or advised on the page, even without a brand name or dose. Put its quantity or dose, if written, in "strength" and how often to take it, if written, in "frequency". Every medicine item must have a name, and appears once with its dose and timing on that same item. Do not include general advice."""


class _Lenient(BaseModel):
    # LLMs sometimes return 7.6 instead of "7.6", or null for a boolean. Accept those forms;
    # anything structurally wrong still fails validation and triggers the retry.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    @field_validator("uncertain", mode="before", check_fields=False)
    @classmethod
    def _none_is_false(cls, v: Any) -> Any:
        return False if v is None else v


class RawObservation(_Lenient):
    label: str
    value: str
    unit: Optional[str] = None
    block_id: Optional[str] = None
    uncertain: bool = False
    note: Optional[str] = None


class RawMedication(_Lenient):
    name: str
    strength: Optional[str] = None
    frequency: Optional[str] = None
    block_id: Optional[str] = None
    uncertain: bool = False
    note: Optional[str] = None


class StructuredPage(_Lenient):
    kind: Literal["lab", "rx", "unknown"] = "unknown"
    source_org: Optional[str] = None
    doc_date: Optional[str] = None
    doc_date_block: Optional[str] = None
    observations: list[RawObservation] = []
    medications: list[RawMedication] = []

    @field_validator("kind", mode="before")
    @classmethod
    def _normalise_kind(cls, v: Any) -> str:
        text = str(v or "").strip().lower()
        if text in {"lab", "lab_report", "lab report", "report", "laboratory"}:
            return "lab"
        if text in {"rx", "prescription"}:
            return "rx"
        return "unknown"

    @field_validator("observations", "medications", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return [] if v is None else v


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if m:
        return m.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def structure_from_blocks(
    blocks: list[ParsedBlock],
    use_cache: bool = True,
    allow_network: bool = True,
) -> StructuredPage:
    """Call text LLM to structure blocks into StructuredPage, retrying once on validation error."""
    block_payload = [
        {"id": b.block_id, "type": b.block_type, "text": b.text}
        for b in blocks
    ]
    messages = [
        {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(block_payload, ensure_ascii=False)},
    ]

    last_error: str | None = None
    for attempt in range(2):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your previous JSON failed validation: {last_error}. Return ONLY valid JSON matching the schema.",
                }
            )
        payload = {
            "model": settings.nvidia_text_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 2048,
            **NO_THINKING,
        }
        resp = chat_completion(payload, use_cache=use_cache, allow_network=allow_network)
        content = message_text(resp)
        try:
            raw_json = _strip_json_fences(content)
            return StructuredPage.model_validate_json(raw_json)
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            messages.append({"role": "assistant", "content": content})

    raise ValueError(f"Structuring failed validation after retry: {last_error}")


def structure_from_image_fallback(
    image_path: Path,
    use_cache: bool = True,
    allow_network: bool = True,
) -> StructuredPage:
    """Fallback vision LLM call when Nemotron Parse returns too few blocks or empty rx."""
    compressed, _, _ = compress_image_for_api(image_path)
    data_url = image_to_data_url(compressed)
    prompt = (
        STRUCTURE_SYSTEM_PROMPT.replace("You receive text blocks, each with an id.", "You receive an image of the page.")
        + '\nYou are reading the image directly, so set every "block_id" to null and "doc_date_block" to null.'
    )
    # Instructions and image go in one user message (OpenAI-style image_url part).
    payload = {
        "model": settings.nvidia_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0,
        "max_tokens": 2048,
        **NO_THINKING,
    }
    resp = chat_completion(payload, use_cache=use_cache, allow_network=allow_network, image_key=file_sha256(image_path))
    content = message_text(resp)
    raw_json = _strip_json_fences(content)
    page = StructuredPage.model_validate_json(raw_json)
    # The fallback has no Parse blocks to point at: never keep a block id the model invented.
    for item in [*page.observations, *page.medications]:
        item.block_id = None
    page.doc_date_block = None
    return page
