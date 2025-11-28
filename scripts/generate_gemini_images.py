#!/usr/bin/env python3
"""
Generate photorealistic property images with Gemini's image endpoint using the prompts
stored in data/unit_image_prompts.json.

Workflow:
1. Load all prompt entries (code, usage, prompt, style add-ons).
2. For each entry, call the Gemini image API N times (default 10), appending the style add-ons
   to steer the generation.
3. Decode the returned base64 image bytes and save them under images_full/<code>/gemini_<idx>.png.
4. Persist a metadata log describing every generated asset.

The script requires GEMINI_API_KEY to be set (same key already used elsewhere in the project).
API spec reference: https://ai.google.dev/gemini-api/docs/image-generation
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, List

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
PROMPT_FILE = DATA_DIR / "unit_image_prompts.json"
DEFAULT_OUTPUT_PARENT = REPO_ROOT / "images_full"
METADATA_FILE = DATA_DIR / "generated_gemini_images.json"

DEFAULT_MODEL = "gemini-2.5-flash-image"
ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate images for units via Gemini API.")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=PROMPT_FILE,
        help="Path to unit_image_prompts.json (default: data/unit_image_prompts.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_PARENT,
        help="Directory where unit folders will be created (default: images_full/)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Gemini image model name (default: models/gemini-2.5-flash-image)",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="1:1",
        help="Aspect ratio supported by the selected model (default: 1:1).",
    )
    parser.add_argument(
        "--image-count",
        type=int,
        default=1,
        help="Number of images to create per unit (default: 1).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.5,
        help="Seconds to sleep between calls to avoid hitting rate limits (default: 1.5).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip generation if the destination file already exists.",
    )
    return parser.parse_args()


def ensure_api_key() -> str:
    """Return the Gemini API key from the environment or exit."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY environment variable is not set.")
    return api_key


def resolve_repo_path(path: Path) -> Path:
    """Resolve user-provided paths relative to the repo root when not absolute."""
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_prompts(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        raise SystemExit(f"Prompt file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("Prompt file must be a list of objects.")
    return data


def compose_prompt(base_prompt: str, style_addons: List[str]) -> str:
    if style_addons:
        style_block = "\nStyle Add-ons: " + ", ".join(style_addons)
    else:
        style_block = ""
    return f"{base_prompt.strip()}{style_block}"


def request_image(
    api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    retry_attempts: int = 3,
    retry_delay: float = 2.0,
) -> bytes:
    endpoint = ENDPOINT_TEMPLATE.format(model=model)
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": aspect_ratio,
            }
        },
    }

    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error {resp.status_code}: {resp.text[:500]}"
                )
            data = resp.json()
            inline_data = extract_inline_image(data)
            if not inline_data:
                raise RuntimeError(
                    f"Response missing inline image data: {json.dumps(data, ensure_ascii=False)[:500]}"
                )
            return base64.b64decode(inline_data)
        except Exception as exc:  # pragma: no cover - network interaction
            last_error = exc
            if attempt == retry_attempts:
                raise
            time.sleep(retry_delay * attempt)
    if last_error:  # safety
        raise last_error
    raise RuntimeError("Unexpected failure requesting image.")


def extract_inline_image(response: Dict[str, object]) -> str | None:
    candidates = response.get("candidates") or []
    if not candidates:
        return None
    first = candidates[0]
    content = first.get("content") or {}
    parts = content.get("parts") or []
    for part in parts:
        inline = part.get("inlineData")
        if inline and inline.get("mimeType", "").startswith("image"):
            return inline.get("data")
    # Some responses return base64 under content.parts[*].inline_data
    for part in parts:
        inline = part.get("inline_data")
        if inline and inline.get("mime_type", "").startswith("image"):
            return inline.get("data")
    return None


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main():
    args = parse_args()
    api_key = ensure_api_key()
    args.prompt_file = resolve_repo_path(args.prompt_file)
    args.output_dir = resolve_repo_path(args.output_dir)
    prompts = load_prompts(args.prompt_file)
    ensure_directory(args.output_dir)

    metadata: List[Dict[str, object]] = []
    processed_units = 0

    for entry in prompts:
        code = str(entry.get("code") or "unknown").replace("/", "_")
        prompt_text = str(entry.get("prompt") or "")
        style_addons = entry.get("style_addons") or []
        if not prompt_text:
            print(f"[WARN] Skipping {code} (empty prompt).")
            continue

        unit_dir = args.output_dir / code
        ensure_directory(unit_dir)
        print(f"Generating images for {code} ...")

        for idx in range(1, args.image_count + 1):
            file_name = f"gemini_{idx:02d}.png"
            file_path = unit_dir / file_name
            if args.skip_existing and file_path.exists():
                print(f"  Skipping existing {file_name}")
                continue

            composed_prompt = compose_prompt(prompt_text, style_addons)
            try:
                image_bytes = request_image(
                    api_key=api_key,
                    model=args.model,
                    prompt=composed_prompt,
                    aspect_ratio=args.aspect_ratio,
                )
            except Exception as exc:
                print(f"  [ERROR] Failed to generate image {idx} for {code}: {exc}")
                break

            file_path.write_bytes(image_bytes)
            metadata.append(
                {
                    "code": entry.get("code"),
                    "usage": entry.get("usage"),
                    "file": str(file_path.relative_to(REPO_ROOT)),
                    "model": args.model,
                    "aspect_ratio": args.aspect_ratio,
                    "prompt": prompt_text,
                    "style_addons": style_addons,
                    "timestamp": time.time(),
                }
            )
            print(f"  Saved {file_name}")
            time.sleep(args.sleep)

        processed_units += 1

    if metadata:
        METADATA_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote metadata for {len(metadata)} images to {METADATA_FILE}")
    print(f"Completed {processed_units} units.")


if __name__ == "__main__":
    main()


