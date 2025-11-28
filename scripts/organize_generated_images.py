#!/usr/bin/env python3
"""
Move generated Gemini images into data/generated_images/ and create a mapping JSON
linking every unit (as listed in data/11-15_sample25.csv) to its corresponding image.

Usage:
    python scripts/organize_generated_images.py

Optional flags allow overriding the CSV, source image directory, destination directory,
output JSON path, and running in dry-run mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_CSV = DATA_DIR / "11-15_sample25.csv"
DEFAULT_SOURCE = REPO_ROOT / "images_full"
DEFAULT_DEST = DATA_DIR / "generated_images"
DEFAULT_OUTPUT_JSON = DATA_DIR / "generated_images_map.json"


@dataclass
class MappingResult:
    code: str
    safe_code: str
    image_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move generated images into data/generated_images/ and build mapping JSON."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="CSV file containing unit data (default: data/11-15_sample25.csv).",
    )
    parser.add_argument(
        "--source-images",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Directory containing per-unit image folders (default: images_full/).",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=DEFAULT_DEST,
        help="Directory where flattened images will be stored (default: data/generated_images/).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help="Path to the JSON mapping file (default: data/generated_images_map.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without moving files or writing JSON.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    """Resolve relative paths against the repository root."""
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def sanitize_code(code: str) -> str:
    """Make a filesystem-safe version of the unit code."""
    return code.replace("/", "_").replace("\\", "_").strip()


def load_units(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader if row.get("Code")]


def pick_image(source_dir: Path) -> Path | None:
    """Return the first PNG image found inside source_dir, if any."""
    pngs = sorted(source_dir.glob("*.png"))
    return pngs[0] if pngs else None


def move_image(src: Path, dest: Path, dry_run: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not dry_run:
        dest.unlink()
    if dry_run:
        print(f"[DRY-RUN] Would move {src} -> {dest}")
    else:
        shutil.move(str(src), str(dest))
        print(f"Moved {src.relative_to(REPO_ROOT)} -> {dest.relative_to(REPO_ROOT)}")


def write_mapping_json(
    output_path: Path,
    entries: Sequence[MappingResult],
    missing: Sequence[Dict[str, str]],
    dry_run: bool,
) -> None:
    payload = {
        "generated_at": time.time(),
        "image_base_dir": str(output_path.parent.relative_to(REPO_ROOT)),
        "entries": [
            {
                "code": entry.code,
                "safe_code": entry.safe_code,
                "image": str(entry.image_path.relative_to(REPO_ROOT)),
            }
            for entry in entries
        ],
        "missing": list(missing),
    }

    if dry_run:
        print(f"[DRY-RUN] Would write mapping JSON to {output_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote mapping JSON with {len(entries)} entries to {output_path}")


def main() -> None:
    args = parse_args()
    csv_path = resolve_path(args.csv)
    source_dir = resolve_path(args.source_images)
    dest_dir = resolve_path(args.dest_dir)
    output_json = resolve_path(args.output_json)

    units = load_units(csv_path)
    mappings: List[MappingResult] = []
    missing: List[Dict[str, str]] = []

    for unit in units:
        code = unit["Code"].strip()
        safe_code = sanitize_code(code)
        unit_source_dir = source_dir / safe_code

        if not unit_source_dir.exists():
            missing.append({"code": code, "reason": "missing source directory"})
            print(f"[WARN] Missing directory for {code}: {unit_source_dir}")
            continue

        img = pick_image(unit_source_dir)
        if not img:
            missing.append({"code": code, "reason": "no PNG files"})
            print(f"[WARN] No PNG files for {code} in {unit_source_dir}")
            continue

        dest_path = dest_dir / f"{safe_code}{img.suffix}"
        move_image(img, dest_path, args.dry_run)
        mappings.append(MappingResult(code=code, safe_code=safe_code, image_path=dest_path))

    write_mapping_json(output_json, mappings, missing, args.dry_run)

    print(
        f"Processed {len(units)} units -> {len(mappings)} moved, {len(missing)} missing/failed."
    )


if __name__ == "__main__":
    main()


