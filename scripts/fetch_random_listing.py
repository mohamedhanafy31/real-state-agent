#!/usr/bin/env python3
"""
Production-ready script to fetch random real-estate listings from online sources.

Setup:
    1. Install dependencies: pip install requests beautifulsoup4 python-dotenv urllib3
    2. Create sources.json with your source configurations
    3. Run: python fetch_random_listing.py --sources sources.json

The script will:
    - Fetch listings from configured HTML and API sources
    - Categorize listings using Arabic/English keywords
    - Return a random listing as structured JSON
    - Handle errors gracefully and respect robots.txt
"""

import argparse
import json
import logging
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Real estate keyword categories (Arabic and English)
REAL_ESTATE_KEYWORDS = {
    "apartment": {
        "en": ["apartment", "flat", "unit", "condo", "studio", "penthouse", "duplex"],
        "ar": ["شقة", "أباتمانت", "يونيت", "استوديو", "بنتهاوس", "دوبلكس", "وحدة"]
    },
    "villa": {
        "en": ["villa", "house", "mansion", "townhouse", "bungalow"],
        "ar": ["فيلا", "منزل", "قصر", "تاون هاوس", "بنجلو"]
    },
    "commercial": {
        "en": ["shop", "store", "office", "commercial", "retail", "warehouse", "showroom"],
        "ar": ["محل", "متجر", "مكتب", "تجاري", "مستودع", "صالة عرض", "معرض"]
    },
    "land": {
        "en": ["land", "plot", "lot", "acre", "farm"],
        "ar": ["أرض", "قطعة أرض", "مزرعة", "فدان"]
    },
    "residential_complex": {
        "en": ["compound", "residential complex", "gated community", "resort"],
        "ar": ["كمباوند", "مجمع سكني", "مجتمع مغلق", "منتجع"]
    },
    "hotel": {
        "en": ["hotel", "resort", "lodge"],
        "ar": ["فندق", "منتجع", "لوج"]
    }
}


def categorize_by_keywords(title: str, description: str = "") -> Dict[str, Any]:
    """
    Categorize a listing based on title and description using keyword matching.
    
    Args:
        title: Listing title
        description: Listing description (optional)
        
    Returns:
        Dictionary with 'category' (list) and 'matched_keywords' (list)
    """
    text = f"{title} {description}".lower()
    matched_categories = []
    matched_keywords = []
    
    # Check each category
    for category, keywords in REAL_ESTATE_KEYWORDS.items():
        category_matches = []
        
        # Check English keywords
        for keyword in keywords["en"]:
            if keyword.lower() in text:
                category_matches.append(keyword)
                matched_keywords.append(keyword)
        
        # Check Arabic keywords
        for keyword in keywords["ar"]:
            if keyword in text:
                category_matches.append(keyword)
                matched_keywords.append(keyword)
        
        # If any keywords matched, add category
        if category_matches:
            matched_categories.append(category)
    
    # If no category matched, default to "other"
    if not matched_categories:
        matched_categories = ["other"]
    
    return {
        "category": matched_categories,
        "matched_keywords": list(set(matched_keywords))  # Remove duplicates
    }


def normalize_url(url: str, base_url: str) -> str:
    """Convert relative URLs to absolute URLs."""
    if not url or url is None:
        return ""
    url = str(url)
    if url.startswith(('http://', 'https://')):
        return url
    return urljoin(base_url, url)


def check_robots_txt(url: str, ignore_robots: bool = False) -> bool:
    """
    Check if URL is allowed by robots.txt.
    
    Args:
        url: URL to check
        ignore_robots: If True, skip robots.txt check
        
    Returns:
        True if allowed, False otherwise
    """
    if ignore_robots:
        return True
    
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception as e:
        logger.warning(f"Error checking robots.txt for {url}: {e}")
        return True  # Allow if check fails


def fetch_html_listing(
    source: Dict[str, Any],
    pages: int = 1,
    delay: float = 1.0,
    ignore_robots: bool = False,
    debug: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetch listings from an HTML source.
    
    Args:
        source: Source configuration dictionary
        pages: Number of pages to crawl
        delay: Delay between requests in seconds
        ignore_robots: Whether to ignore robots.txt
        
    Returns:
        List of listing dictionaries
    """
    listings = []
    base_url = source["url"]
    
    try:
        for page in range(1, pages + 1):
            # Build URL with page parameter
            if "?" in base_url:
                page_url = f"{base_url}&page={page}"
            else:
                page_url = f"{base_url}?page={page}"
            
            # Check robots.txt
            if not check_robots_txt(page_url, ignore_robots):
                logger.warning(f"robots.txt disallows: {page_url}")
                continue
            
            # Fetch page
            try:
                response = requests.get(page_url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Error fetching {page_url}: {e}")
                continue
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            list_item_selector = source.get("list_item_selector", "")
            list_items = soup.select(list_item_selector)
            
            if not list_items:
                logger.warning(f"No items found with selector '{list_item_selector}' on {page_url}")
                # Try to provide helpful debugging info
                logger.debug(f"Page content length: {len(response.content)} bytes")
                # Save HTML sample in debug mode
                if debug:
                    import os
                    debug_dir = "debug_html"
                    os.makedirs(debug_dir, exist_ok=True)
                    safe_name = (source.get("name") or "unknown").replace(" ", "_").lower()
                    debug_file = os.path.join(debug_dir, f"{safe_name}_page{page}.html")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    logger.debug(f"Saved HTML sample to {debug_file} for inspection")
                break  # No more pages likely
            
            logger.debug(f"Found {len(list_items)} items with selector '{list_item_selector}' on page {page}")
            
            # Extract listings
            items_without_title = 0
            for item in list_items:
                try:
                    listing = {}
                    
                    # Extract title
                    title_selector = source.get("title_selector") or ""
                    title_elem = item.select_one(title_selector) if title_selector else None
                    listing["title"] = title_elem.get_text(strip=True) if title_elem else ""
                    
                    if not listing["title"]:
                        items_without_title += 1
                        logger.debug(f"Title not found with selector '{title_selector}' in item")
                    
                    # Extract price
                    price_selector = source.get("price_selector") or ""
                    price_elem = item.select_one(price_selector) if price_selector else None
                    listing["price"] = price_elem.get_text(strip=True) if price_elem else None
                    
                    # Extract location
                    location_selector = source.get("location_selector") or ""
                    location_elem = item.select_one(location_selector) if location_selector else None
                    listing["location"] = location_elem.get_text(strip=True) if location_elem else None
                    
                    # Extract image
                    image_selector = source.get("image_selector") or ""
                    image_elem = item.select_one(image_selector) if image_selector else None
                    if image_elem:
                        image_url = image_elem.get("src") or image_elem.get("data-src") or image_elem.get("data-lazy-src") or ""
                        listing["image"] = normalize_url(image_url, page_url) if image_url else None
                    else:
                        listing["image"] = None
                    
                    # Extract link
                    link_selector = source.get("link_selector") or ""
                    link_elem = item.select_one(link_selector) if link_selector else None
                    if link_elem:
                        link_url = link_elem.get("href") or ""
                        listing["link"] = normalize_url(link_url, page_url) if link_url else None
                    else:
                        listing["link"] = None
                    
                    # Ensure all values are strings or None, not other types
                    for key in ["title", "price", "location", "description", "image", "link"]:
                        if listing.get(key) is not None and not isinstance(listing[key], str):
                            listing[key] = str(listing[key]) if listing[key] else None
                    
                    # Extract description (if selector provided)
                    desc_selector = source.get("description_selector") or ""
                    desc_elem = item.select_one(desc_selector) if desc_selector else None
                    listing["description"] = desc_elem.get_text(strip=True) if desc_elem else None
                    
                    # Only add if title exists
                    if listing["title"]:
                        listing["source_name"] = source["name"]
                        listing["source_url"] = page_url
                        listings.append(listing)
                
                except Exception as e:
                    import traceback
                    logger.warning(f"Error extracting listing from item: {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                    continue
            
            if items_without_title > 0:
                logger.warning(f"Found {len(list_items)} items but {items_without_title} had no title (check title_selector: '{source.get('title_selector')}')")
                # Save sample HTML in debug mode
                if debug and list_items:
                    import os
                    debug_dir = "debug_html"
                    os.makedirs(debug_dir, exist_ok=True)
                    safe_name = (source.get("name") or "unknown").replace(" ", "_").lower()
                    debug_file = os.path.join(debug_dir, f"{safe_name}_sample_item.html")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(str(list_items[0].prettify()))
                    logger.debug(f"Saved sample item HTML to {debug_file} for inspection")
            
            # Delay between pages
            if page < pages:
                time.sleep(delay)
    
    except Exception as e:
        logger.error(f"Error processing HTML source {source['name']}: {e}")
    
    return listings


def get_nested_value(data: Any, path: str, default: Any = None) -> Any:
    """
    Get a nested value from a dictionary/list using dot notation.
    
    Args:
        data: Dictionary or list to navigate
        path: Dot-separated path (e.g., "location.name" or "images.main")
        default: Default value if path not found
        
    Returns:
        Value at path or default
    """
    if not path:
        return data
    
    keys = path.split(".")
    current = data
    
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and key.isdigit():
            try:
                current = current[int(key)]
            except (IndexError, ValueError):
                return default
        else:
            return default
        
        if current is None:
            return default
    
    return current


def fetch_api_listing(
    source: Dict[str, Any],
    pages: int = 1,
    delay: float = 1.0,
    ignore_robots: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetch listings from an API source.
    
    Args:
        source: Source configuration dictionary
        pages: Number of pages to fetch
        delay: Delay between requests in seconds
        ignore_robots: Whether to ignore robots.txt
        
    Returns:
        List of listing dictionaries
    """
    listings = []
    api_url = source.get("api_url", source.get("url", ""))
    results_path = source.get("results_path", "results")  # JSON path to results array
    http_method = source.get("method", "GET").upper()
    custom_headers = source.get("headers", {})
    
    try:
        for page in range(1, pages + 1):
            # Build URL with page parameter
            if "?" in api_url:
                page_url = f"{api_url}&page={page}"
            else:
                page_url = f"{api_url}?page={page}"
            
            # Check robots.txt
            if not check_robots_txt(page_url, ignore_robots):
                logger.warning(f"robots.txt disallows: {page_url}")
                continue
            
            # Prepare headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            headers.update(custom_headers)
            
            # Fetch API
            try:
                if http_method == "GET":
                    response = requests.get(page_url, timeout=10, headers=headers)
                elif http_method == "POST":
                    response = requests.post(page_url, timeout=10, headers=headers)
                else:
                    logger.error(f"Unsupported HTTP method: {http_method}")
                    continue
                
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                logger.error(f"Error fetching API {page_url}: {e}")
                continue
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from {page_url}: {e}")
                continue
            
            # Navigate JSON path to results array
            results = data
            for key in results_path.split("."):
                if isinstance(results, dict):
                    results = results.get(key, [])
                elif isinstance(results, list):
                    break
                else:
                    results = []
                    break
            
            if not isinstance(results, list):
                logger.warning(f"Results path '{results_path}' does not point to an array in {page_url}")
                break
            
            if not results:
                break  # No more pages likely
            
            # Get field mapping (support both field_mapping and field_map)
            field_mapping = source.get("field_mapping") or source.get("field_map", {})
            
            # Extract listings
            for item in results:
                try:
                    listing = {}
                    
                    # Map API fields to listing fields using nested path support
                    title_path = field_mapping.get("title", "title")
                    listing["title"] = get_nested_value(item, title_path, "") or ""
                    
                    price_path = field_mapping.get("price", "price")
                    listing["price"] = get_nested_value(item, price_path)
                    
                    location_path = field_mapping.get("location", "location")
                    listing["location"] = get_nested_value(item, location_path)
                    
                    desc_path = field_mapping.get("description", "description")
                    listing["description"] = get_nested_value(item, desc_path)
                    
                    image_path = field_mapping.get("image", "image")
                    listing["image"] = get_nested_value(item, image_path)
                    
                    link_path = field_mapping.get("link") or field_mapping.get("url", "link")
                    listing["link"] = get_nested_value(item, link_path)
                    
                    # Normalize URLs
                    if listing.get("image"):
                        listing["image"] = normalize_url(str(listing["image"]), api_url)
                    if listing.get("link"):
                        listing["link"] = normalize_url(str(listing["link"]), api_url)
                    
                    # Only add if title exists
                    if listing["title"]:
                        listing["source_name"] = source["name"]
                        listing["source_url"] = page_url
                        listings.append(listing)
                
                except Exception as e:
                    logger.warning(f"Error extracting listing from API item: {e}")
                    continue
            
            # Delay between pages
            if page < pages:
                time.sleep(delay)
    
    except Exception as e:
        logger.error(f"Error processing API source {source['name']}: {e}")
    
    return listings


def remove_duplicates(listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate listings based on link or title similarity.
    
    Args:
        listings: List of listing dictionaries
        
    Returns:
        Deduplicated list
    """
    seen_links = set()
    seen_titles = set()
    unique_listings = []
    
    for listing in listings:
        link = listing.get("link", "")
        title = listing.get("title", "").lower().strip()
        
        # Skip if link already seen
        if link and link in seen_links:
            continue
        
        # Skip if title already seen (simple exact match)
        if title and title in seen_titles:
            continue
        
        if link:
            seen_links.add(link)
        if title:
            seen_titles.add(title)
        
        unique_listings.append(listing)
    
    return unique_listings


def format_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a listing into the final JSON structure.
    
    Args:
        listing: Raw listing dictionary
        
    Returns:
        Formatted listing dictionary
    """
    title = listing.get("title", "")
    description = listing.get("description", "")
    
    # Categorize
    categorization = categorize_by_keywords(title, description or "")
    
    # Build final structure
    formatted = {
        "id": str(uuid.uuid4()),
        "title": title,
        "category": categorization["category"],
        "matched_keywords": categorization["matched_keywords"],
        "price": listing.get("price"),
        "location": listing.get("location"),
        "description": description,
        "image": listing.get("image"),
        "source_name": listing.get("source_name", ""),
        "source_url": listing.get("source_url", ""),
        "scraped_at": datetime.now(timezone.utc).isoformat()
    }
    
    return formatted


def test_categorize_by_keywords():
    """
    Unit-test style example function for categorize_by_keywords.
    Tests various scenarios with Arabic and English keywords.
    """
    test_cases = [
        {
            "title": "شقة للبيع في القاهرة",
            "description": "شقة جميلة في منطقة هادئة",
            "expected_categories": ["apartment"],
            "expected_keywords": ["شقة"]
        },
        {
            "title": "Villa for Sale in New Cairo",
            "description": "Beautiful villa with garden",
            "expected_categories": ["villa"],
            "expected_keywords": ["villa"]
        },
        {
            "title": "Commercial Office Space",
            "description": "Shop available for rent",
            "expected_categories": ["commercial"],
            "expected_keywords": ["office", "shop"]
        },
        {
            "title": "أرض للبيع - قطعة أرض",
            "description": "مزرعة كبيرة",
            "expected_categories": ["land"],
            "expected_keywords": ["أرض", "قطعة أرض", "مزرعة"]
        },
        {
            "title": "Apartment in Residential Complex",
            "description": "Gated community with amenities",
            "expected_categories": ["apartment", "residential_complex"],
            "expected_keywords": ["apartment", "complex", "community"]
        },
        {
            "title": "Unknown Property Type",
            "description": "Some property description",
            "expected_categories": ["other"],
            "expected_keywords": []
        }
    ]
    
    print("Testing categorize_by_keywords function:", file=sys.stderr)
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        result = categorize_by_keywords(
            test_case["title"],
            test_case.get("description", "")
        )
        
        # Check categories (order doesn't matter)
        categories_match = set(result["category"]) == set(test_case["expected_categories"])
        
        # Check keywords (at least some should match)
        keywords_match = any(
            kw in result["matched_keywords"]
            for kw in test_case["expected_keywords"]
        ) if test_case["expected_keywords"] else len(result["matched_keywords"]) == 0
        
        if categories_match and keywords_match:
            print(f"  Test {i}: PASSED", file=sys.stderr)
            passed += 1
        else:
            print(f"  Test {i}: FAILED", file=sys.stderr)
            print(f"    Expected categories: {test_case['expected_categories']}", file=sys.stderr)
            print(f"    Got categories: {result['category']}", file=sys.stderr)
            print(f"    Expected keywords (some): {test_case['expected_keywords']}", file=sys.stderr)
            print(f"    Got keywords: {result['matched_keywords']}", file=sys.stderr)
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed", file=sys.stderr)
    return failed == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch a random real-estate listing from configured sources"
    )
    parser.add_argument(
        "--sources",
        default="sources.json",
        help="Path to sources.json configuration file (default: sources.json)"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Number of pages to crawl per source (default: 1)"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        help="Maximum number of candidates to collect (default: 50)"
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt restrictions"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run unit tests for categorize_by_keywords function"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save output JSON to file (default: print to stdout)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of random listings to return (default: 1)"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests if requested
    if args.test:
        success = test_categorize_by_keywords()
        sys.exit(0 if success else 1)
    
    # Load sources configuration
    try:
        with open(args.sources, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Sources file not found: {args.sources}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing sources.json: {e}")
        sys.exit(1)
    
    # Handle both formats: direct array or object with "sources" key
    if isinstance(data, list):
        sources = data
    elif isinstance(data, dict) and "sources" in data:
        sources = data["sources"]
    else:
        logger.error("sources.json must contain a JSON array or an object with a 'sources' key")
        sys.exit(1)
    
    if not isinstance(sources, list):
        logger.error("sources must be a JSON array")
        sys.exit(1)
    
    # Collect listings from all sources
    all_listings = []
    
    for source in sources:
        source_type = source.get("type", "").lower()
        source_name = source.get("name", "Unknown")
        
        logger.info(f"Processing source: {source_name} (type: {source_type})")
        
        if source_type == "html":
            listings = fetch_html_listing(
                source,
                pages=args.pages,
                delay=args.delay,
                ignore_robots=args.ignore_robots,
                debug=args.debug
            )
        elif source_type == "api":
            listings = fetch_api_listing(
                source,
                pages=args.pages,
                delay=args.delay,
                ignore_robots=args.ignore_robots
            )
        else:
            logger.warning(f"Unknown source type '{source_type}' for source '{source_name}'")
            continue
        
        logger.info(f"Found {len(listings)} listings from {source_name}")
        all_listings.extend(listings)
        
        # Stop if we have enough candidates
        if len(all_listings) >= args.max:
            break
    
    # Limit to max candidates
    all_listings = all_listings[:args.max]
    
    # Remove duplicates
    all_listings = remove_duplicates(all_listings)
    
    if not all_listings:
        logger.error("No listings found from any source")
        sys.exit(1)
    
    # Pick random listings
    count = min(args.count, len(all_listings))
    selected = random.sample(all_listings, count)
    
    # Format listings
    formatted_listings = [format_listing(listing) for listing in selected]
    
    # Output as array if multiple, single object if one
    if count == 1:
        output_json = json.dumps(formatted_listings[0], ensure_ascii=False, indent=2)
    else:
        output_json = json.dumps(formatted_listings, ensure_ascii=False, indent=2)
    
    if args.output:
        # Save to file
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        logger.info(f"Results saved to {args.output} ({count} listing(s))")
    else:
        # Print to stdout
        print(output_json)


if __name__ == "__main__":
    main()

