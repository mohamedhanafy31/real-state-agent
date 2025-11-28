#!/usr/bin/env python3
"""
Download images from real estate listings JSON file.

Usage:
    python download_listing_images.py --input samples_30.json --output-dir images/
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def get_file_extension(url: str) -> str:
    """Get file extension from URL."""
    parsed = urlparse(url)
    path = parsed.path
    # Remove query parameters
    if '?' in path:
        path = path.split('?')[0]
    # Get extension
    ext = os.path.splitext(path)[1]
    if not ext:
        # Try to get from content-type or default to .jpg
        return '.jpg'
    return ext.lower()


def get_full_quality_url(url: str, listing_link: str = None) -> str:
    """
    Convert thumbnail URL to full quality URL.
    Tries multiple strategies to get the best quality image.
    
    Handles:
    - PropertyFinder: Try different size dimensions or remove query params
    - Aqarmap: Try different path patterns
    """
    if not url:
        return url
    
    # PropertyFinder pattern: /property/.../416/272/MODE/...
    if 'propertyfinder.eg' in url:
        # Try removing query parameters first (sometimes helps)
        base_url = url.split('?')[0]
        
        # Try different size dimensions
        size_replacements = [
            ('/416/272/', '/1920/1080/'),  # Full HD
            ('/416/272/', '/1600/1200/'),  # Large
            ('/416/272/', '/1200/900/'),   # Medium-large
            ('/416/272/', '/800/600/'),    # Medium
        ]
        
        for old_size, new_size in size_replacements:
            if old_size in base_url:
                test_url = base_url.replace(old_size, new_size)
                # Test if URL exists
                try:
                    response = requests.head(test_url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        return test_url
                except:
                    pass
        
        # If no size replacement worked, try removing size constraint entirely
        if '/416/272/' in base_url:
            # Try without size (some APIs serve original when size is omitted)
            test_url = base_url.replace('/416/272/', '/')
            try:
                response = requests.head(test_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    return test_url
            except:
                pass
    
    # Aqarmap pattern: search-thumb-webp
    if 'aqarmap.com.eg' in url:
        # Try different path patterns
        patterns = [
            ('search-thumb-webp', 'original-webp'),
            ('search-thumb-webp', 'large-webp'),
            ('search-thumb-webp', 'full-webp'),
            ('search-thumb-webp', 'webp'),  # Remove search-thumb prefix
        ]
        
        for old_pattern, new_pattern in patterns:
            if old_pattern in url:
                test_url = url.replace(old_pattern, new_pattern)
                try:
                    response = requests.head(test_url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        return test_url
                except:
                    pass
    
    # For other sources, try common patterns
    if '/thumb' in url.lower() or '/thumbnail' in url.lower():
        test_url = url.replace('/thumb', '/full').replace('/thumbnail', '/full')
        try:
            response = requests.head(test_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return test_url
        except:
            pass
    
    # If no pattern matches or all tests failed, return original URL
    return url


def download_image(url: str, output_path: str, timeout: int = 30) -> bool:
    """Download an image from URL to output path."""
    try:
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.raise_for_status()
        
        # Save image
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download images from real estate listings JSON file"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file with listings"
    )
    parser.add_argument(
        "--output-dir",
        default="images",
        help="Output directory for images (default: images/)"
    )
    parser.add_argument(
        "--name-by",
        choices=["id", "title", "index"],
        default="id",
        help="How to name files: 'id' (UUID), 'title', or 'index' (default: id)"
    )
    parser.add_argument(
        "--full-quality",
        action="store_true",
        help="Download full quality images (convert thumbnail URLs to full-size)"
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
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download images
    downloaded = 0
    skipped = 0
    failed = 0
    
    for idx, listing in enumerate(listings):
        image_url = listing.get("image")
        if not image_url:
            print(f"[{idx+1}/{len(listings)}] Skipping (no image URL): {listing.get('title', 'Unknown')[:50]}")
            skipped += 1
            continue
        
        # Convert to full quality if requested
        if args.full_quality:
            original_url = image_url
            listing_link = listing.get("link") or listing.get("source_url", "")
            image_url = get_full_quality_url(image_url, listing_link)
            if image_url != original_url:
                print(f"[{idx+1}/{len(listings)}] Trying full quality URL...")
        
        # Determine filename
        if args.name_by == "id":
            base_name = listing.get("id", f"listing_{idx}")
        elif args.name_by == "title":
            title = listing.get("title", f"listing_{idx}")
            base_name = sanitize_filename(title)
        else:  # index
            base_name = f"listing_{idx:03d}"
        
        # Get file extension
        ext = get_file_extension(image_url)
        filename = f"{base_name}{ext}"
        output_path = output_dir / filename
        
        # Skip if already exists
        if output_path.exists():
            print(f"[{idx+1}/{len(listings)}] Already exists: {filename}")
            skipped += 1
            continue
        
        # Download
        print(f"[{idx+1}/{len(listings)}] Downloading: {filename}...", end=" ", flush=True)
        if download_image(image_url, str(output_path)):
            file_size = output_path.stat().st_size
            print(f"✓ ({file_size:,} bytes)")
            downloaded += 1
        else:
            # If full quality failed, try original URL as fallback
            if args.full_quality and image_url != listing.get("image"):
                print(f"\n  Trying original URL...", end=" ", flush=True)
                if download_image(listing.get("image"), str(output_path)):
                    file_size = output_path.stat().st_size
                    print(f"✓ ({file_size:,} bytes) [fallback]")
                    downloaded += 1
                else:
                    print("✗ Failed")
                    failed += 1
            else:
                print("✗ Failed")
                failed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(listings)}")
    print(f"  Output directory: {output_dir.absolute()}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

