#!/usr/bin/env python3
"""
Generate high-quality image prompts for each real-estate unit by calling Gemini.

Steps:
1. Read rows from the sample CSV that already includes enriched descriptions.
2. For every unit, send a structured fact sheet to the Gemini text model.
3. Parse the JSON response (prompt + style add-ons) and store it back in a new column.
4. Persist results into both CSV and XLSX as well as a standalone JSON file.

The script expects the environment variable GEMINI_API_KEY to be set.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

try:
    import google.generativeai as genai
except ImportError as exc:  # pragma: no cover - dependency check
    raise SystemExit(
        "google-generativeai is required. Install it with: pip install google-generativeai"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
INPUT_CSV = DATA_DIR / "11-15_sample25.csv"
INPUT_XLSX = DATA_DIR / "11-15_sample25.xlsx"
OUTPUT_CSV = DATA_DIR / "11-15_sample25.csv"
OUTPUT_XLSX = DATA_DIR / "11-15_sample25.xlsx"
OUTPUT_JSON = DATA_DIR / "unit_image_prompts.json"

MODEL_NAME = os.getenv("GEMINI_PROMPT_MODEL", "models/gemini-2.0-flash")
MAX_RETRIES = 3
SLEEP_BASE_SECONDS = 2


def ensure_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY environment variable is not set.")
    return api_key


def load_dataframe() -> pd.DataFrame:
    if INPUT_CSV.exists():
        df = pd.read_csv(INPUT_CSV)
    elif INPUT_XLSX.exists():
        df = pd.read_excel(INPUT_XLSX)
    else:
        raise SystemExit("Neither CSV nor XLSX source file was found.")
    return df


def build_fact_sheet(row: pd.Series) -> str:
    def _fmt(value) -> str:
        if pd.isna(value):
            return "N/A"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    facts = {
        "Name": _fmt(row.get("Name")),
        "Code": _fmt(row.get("Code")),
        "Project": _fmt(row.get("Project")),
        "Building": _fmt(row.get("Building")),
        "Usage": _fmt(row.get("Usage")),
        "Area_m2": _fmt(row.get("Area")),
        "Garden_m2": _fmt(row.get("Garden")),
        "Roof_m2": _fmt(row.get("Roof")),
        "Floor": _fmt(row.get("Floor")),
        "Price_EGP": _fmt(row.get("Price")),
        "LocationCard": _fmt(row.get("Location")),
        "ArabicDescription": _fmt(row.get("Description")),
    }

    serialized = "\n".join(f"{key}: {value}" for key, value in facts.items())
    return serialized


def build_user_prompt(row: pd.Series) -> str:
    instructions = """
You are an expert real-estate creative director crafting detailed prompts for a photorealistic
property image generator. Given the fact sheet, produce a concise English art-direction brief that
captures:
- Property type, size, and standout spatial features
- Views or surroundings (garden, pool, sea, clubhouse, skyline, etc.)
- Finishing level, materials, and architectural style
- Amenities (private garden, rooftop, pool, club facilities, security, etc.)
- Desired atmosphere (lighting, mood, time of day) and camera guidance

RESPONSE FORMAT (JSON ONLY):
{
  "prompt": "<1-3 paragraphs in English describing the exact scene to render. Mention exterior/interior context, views, finishes, and amenities.>",
  "style_addons": [
     "<short stylistic add-on 1>",
     "<short stylistic add-on 2>",
     "<short stylistic add-on 3>"
  ]
}

Notes:
- Keep the prompt grounded in the fact sheet (no fictional data).
- Prefer luxurious but realistic language—this will be the final input to an image generator.
- Style add-ons should be concise (e.g., "8K ultra-realistic", "dawn golden light").
"""
    fact_sheet = build_fact_sheet(row)
    return f"{instructions.strip()}\n\nFACT SHEET:\n{fact_sheet}\n"


def normalize_response(raw_text: str) -> Tuple[str, List[str]]:
    """Extract prompt and style_addons from Gemini's JSON answer."""
    text = raw_text.strip()
    if text.startswith("```"):
        # Remove optional code fences
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        payload: Dict[str, object] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response is not valid JSON: {text}") from exc

    prompt = str(payload.get("prompt", "")).strip()
    style_addons_raw = payload.get("style_addons") or []
    if isinstance(style_addons_raw, str):
        style_addons = [style_addons_raw.strip()]
    else:
        style_addons = [str(item).strip() for item in style_addons_raw if str(item).strip()]

    if not prompt:
        raise ValueError("Gemini response missing 'prompt'.")

    return prompt, style_addons


def call_gemini(model, user_prompt: str) -> Tuple[str, List[str]]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                user_prompt,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_output_tokens": 768,
                },
            )
            return normalize_response(response.text or "")
        except Exception as exc:  # pragma: no cover - network interaction
            if attempt == MAX_RETRIES:
                raise
            sleep_for = SLEEP_BASE_SECONDS * attempt
            time.sleep(sleep_for)
            continue


def main():
    ensure_api_key()
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL_NAME)

    df = load_dataframe()
    prompts_payload = []

    if "GeminiPrompt" not in df.columns:
        df["GeminiPrompt"] = ""

    for idx, row in df.iterrows():
        user_prompt = build_user_prompt(row)
        prompt_text, style_addons = call_gemini(model, user_prompt)
        style_section = ""
        if style_addons:
            style_lines = "\n".join(f"- {addon}" for addon in style_addons)
            style_section = f"\nStyle Add-ons:\n{style_lines}"
        final_prompt = f"{prompt_text}{style_section}"
        df.at[idx, "GeminiPrompt"] = final_prompt
        prompts_payload.append(
            {
                "code": row.get("Code"),
                "usage": row.get("Usage"),
                "prompt": prompt_text,
                "style_addons": style_addons,
            }
        )

    df.to_csv(OUTPUT_CSV, index=False)
    if INPUT_XLSX.exists():
        df.to_excel(OUTPUT_XLSX, index=False)

    OUTPUT_JSON.write_text(json.dumps(prompts_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated prompts for {len(prompts_payload)} units using model {MODEL_NAME}.")
    print(f"- Updated CSV: {OUTPUT_CSV}")
    if INPUT_XLSX.exists():
        print(f"- Updated XLSX: {OUTPUT_XLSX}")
    print(f"- JSON dump: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()


