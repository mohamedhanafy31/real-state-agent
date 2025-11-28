#!/usr/bin/env python3
"""
Create a JSON mapping between image file paths and their listing content.

Usage:
    python create_image_mapping.py --input samples_30.json --images-dir images_full/ --output image_mapping.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def get_file_extension(url: str) -> str:
    """Get file extension from URL."""
    parsed = urlparse(url)
    path = parsed.path
    if '?' in path:
        path = path.split('?')[0]
    ext = os.path.splitext(path)[1]
    if not ext:
        return '.jpg'
    return ext.lower()


def main():
    parser = argparse.ArgumentParser(
        description="Create JSON mapping between image paths and listing content"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file with listings"
    )
    parser.add_argument(
        "--images-dir",
        default="images_full",
        help="Directory containing images (default: images_full/)"
    )
    parser.add_argument(
        "--output",
        default="image_mapping.json",
        help="Output JSON file (default: image_mapping.json)"
    )
    parser.add_argument(
        "--name-by",
        choices=["id", "title", "index"],
        default="id",
        help="How images are named: 'id' (UUID), 'title', or 'index' (default: id)"
    )
    
    args = parser.parse_args()
    
    # Load listings
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Handle both single object and array
    if isinstance(data, dict):
        listings = [data]
    elif isinstance(data, list):
        listings = data
    else:
        print(f"Error: JSON must be an object or array", file=sys.stderr)
        sys.exit(1)
    
    # Check images directory
    images_dir = Path(args.images_dir)
    if not images_dir.exists():
        print(f"Warning: Images directory not found: {images_dir}", file=sys.stderr)
    
    # Create mapping
    mapping = {}
    
    for idx, listing in enumerate(listings):
        listing_id = listing.get("id", f"listing_{idx}")
        image_url = listing.get("image")
        
        if not image_url:
            continue
        
        # Determine image filename based on naming convention
        if args.name_by == "id":
            base_name = listing_id
        elif args.name_by == "title":
            title = listing.get("title", f"listing_{idx}")
            # Sanitize filename
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                title = title.replace(char, '_')
            if len(title) > 200:
                title = title[:200]
            base_name = title
        else:  # index
            base_name = f"listing_{idx:03d}"
        
        # Get file extension
        ext = get_file_extension(image_url)
        image_filename = f"{base_name}{ext}"
        image_path = str(images_dir / image_filename)
        
        # Check if image file exists
        image_exists = (images_dir / image_filename).exists()
        
        # Create mapping entry
        mapping[image_path] = {
            "listing": listing,
            "image_exists": image_exists,
            "image_url": image_url,
            "image_filename": image_filename
        }
    
    # Save mapping
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    # Summary
    total = len(mapping)
    existing = sum(1 for v in mapping.values() if v["image_exists"])
    
    print(f"Created mapping file: {args.output}")
    print(f"Total entries: {total}")
    print(f"Images found: {existing}")
    print(f"Images missing: {total - existing}")


if __name__ == "__main__":
    main()

