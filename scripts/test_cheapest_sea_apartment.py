#!/usr/bin/env python3
"""
Test script to verify if the selector retrieves the cheapest apartment with sea view
when querying "طب اي ارخص شقة بتطل علي البحر"
"""

import sys
import os
from pathlib import Path

# Add the ai/rag directory to path
project_root = Path(__file__).parent
rag_dir = project_root / "ai" / "rag"
sys.path.insert(0, str(rag_dir))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = rag_dir / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

import requests
import json

# Expected: The cheapest apartment with sea view
# From CSV analysis:
# - Hawabay/02/L/304: Apartment, 5,760,000 - has sea view ✓
# - Hawabay/06/M/302: Apartment, 6,346,000 - has sea view ✓
EXPECTED_CHEAPEST = {
    "code": "Hawabay/02/L/304",
    "price": 5760000,
    "name": "304",
    "usage": "Apartment"
}

def test_cheapest_sea_apartment():
    """Test the selector with the cheapest apartment with sea view query."""
    
    # Check if API key is set
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        return False
    
    # Test query
    query = "طب اي ارخص شقة بتطل علي البحر"
    
    print("=" * 70)
    print("Testing Unit Selector - Cheapest Apartment with Sea View")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"\nExpected result:")
    print(f"  Code: {EXPECTED_CHEAPEST['code']}")
    print(f"  Price: {EXPECTED_CHEAPEST['price']:,} EGP")
    print(f"  Name: {EXPECTED_CHEAPEST['name']}")
    print(f"  Usage: {EXPECTED_CHEAPEST['usage']}")
    print()
    
    # Try to use the API endpoint if server is running
    api_url = "http://localhost:8000/selector/test"
    
    try:
        print("Attempting to connect to API server...")
        response = requests.post(
            api_url,
            json={
                "question": query,
                "max_rows": 5  # Should return 1, but allow a few
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Connected to API server")
            print()
            return analyze_result(result, query)
        else:
            print(f"API returned status {response.status_code}")
            print("Falling back to direct selector test...")
    except requests.exceptions.ConnectionError:
        print("⚠ API server not running, testing selector directly...")
    except Exception as e:
        print(f"⚠ Error connecting to API: {e}")
        print("Falling back to direct selector test...")
    
    # Fallback: test selector directly
    print("\nTesting selector directly...")
    try:
        from src.selector import UnitSelector
        from src.utils import load_config, get_config_value
        
        # Find CSV file
        csv_path = rag_dir / "data" / "11-15_sample25.csv"
        if not csv_path.exists():
            csv_path = project_root / "data" / "11-15_sample25.csv"
        
        if not csv_path.exists():
            print(f"ERROR: CSV file not found at {csv_path}")
            return False
        
        print(f"Using CSV: {csv_path}")
        
        # Load config
        config = load_config("config/settings.yaml")
        model_name = get_config_value(config, 'generator.model_name', 'gemini-2.0-flash')
        
        # Initialize selector
        selector = UnitSelector(
            csv_path=str(csv_path),
            api_key=api_key,
            model_name=model_name,
            max_rows=5
        )
        
        # Run selector
        print(f"\nRunning selector with query: '{query}'...")
        result = selector.select_units(query)
        
        # Convert to dict format similar to API response
        result_dict = {
            "success": result.success,
            "question": query,
            "code": result.code,
            "num_units": len(result.rows),
            "units": result.rows,
            "error": result.error,
            "raw_response": result.raw_response,
            "relevance_score": result.relevance_score
        }
        
        return analyze_result(result_dict, query)
        
    except Exception as e:
        print(f"ERROR: Failed to test selector: {e}")
        import traceback
        traceback.print_exc()
        return False


def analyze_result(result, query):
    """Analyze the selector result."""
    
    print("=" * 70)
    print("SELECTOR RESULTS")
    print("=" * 70)
    
    if not result.get("success", False):
        print("❌ Selector failed!")
        if result.get("error"):
            print(f"Error: {result['error']}")
        return False
    
    relevance_score = result.get("relevance_score")
    if relevance_score is not None:
        print(f"Relevance Score: {relevance_score:.2f} ({relevance_score*100:.0f}%)")
        if relevance_score < 0.5:
            print("⚠ Warning: Low relevance score - query may not match CSV data well")
    else:
        print("Relevance Score: Not provided")
    
    print(f"\nNumber of units retrieved: {result.get('num_units', 0)}")
    
    retrieved_units = result.get("units", [])
    
    if not retrieved_units:
        print("\n❌ No units retrieved!")
        print("\nGenerated code:")
        print("-" * 70)
        print(result.get("code", "No code generated"))
        print("-" * 70)
        return False
    
    print("\nRetrieved units:")
    for i, unit in enumerate(retrieved_units, 1):
        code = unit.get("Code") or unit.get("code")
        name = unit.get("Name") or unit.get("name", "N/A")
        price = unit.get("Price") or unit.get("price", 0)
        usage = unit.get("Usage") or unit.get("usage", "N/A")
        description = unit.get("Description") or unit.get("description", "")
        
        has_sea = "بحر" in description or "sea view" in description.lower() or "beach view" in description.lower()
        is_apartment = usage == "Apartment" or "شقة" in usage or "apartment" in usage.lower()
        
        marker = "✓" if (has_sea and is_apartment) else "?"
        print(f"  {marker} {i}. {code}")
        print(f"      Name: {name}, Usage: {usage}, Price: {price:,} EGP")
        if has_sea:
            print(f"      → Contains sea view keywords")
        if not is_apartment:
            print(f"      ⚠ Warning: Not an apartment (Usage: {usage})")
    
    # Check the first result (should be cheapest)
    first_unit = retrieved_units[0]
    first_code = first_unit.get("Code") or first_unit.get("code")
    first_price = first_unit.get("Price") or first_unit.get("price", 0)
    first_usage = first_unit.get("Usage") or first_unit.get("usage", "")
    first_description = first_unit.get("Description") or first_unit.get("description", "")
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    # Check if first result is an apartment
    is_apartment = first_usage == "Apartment" or "شقة" in first_usage or "apartment" in first_usage.lower()
    has_sea = "بحر" in first_description or "sea view" in first_description.lower() or "beach view" in first_description.lower()
    is_cheapest = first_code == EXPECTED_CHEAPEST["code"]
    
    print(f"\nFirst result (should be cheapest apartment with sea view):")
    print(f"  Code: {first_code}")
    print(f"  Price: {first_price:,} EGP")
    print(f"  Usage: {first_usage}")
    print()
    
    checks = []
    
    if is_apartment:
        print("  ✓ Is an apartment")
        checks.append(True)
    else:
        print(f"  ❌ NOT an apartment (Usage: {first_usage})")
        checks.append(False)
    
    if has_sea:
        print("  ✓ Has sea view (contains 'بحر' or sea view keywords)")
        checks.append(True)
    else:
        print("  ❌ Does NOT have sea view")
        checks.append(False)
    
    if is_cheapest:
        print(f"  ✓ Is the expected cheapest unit ({EXPECTED_CHEAPEST['code']})")
        checks.append(True)
    else:
        print(f"  ⚠ Not the expected cheapest unit")
        print(f"     Expected: {EXPECTED_CHEAPEST['code']} ({EXPECTED_CHEAPEST['price']:,} EGP)")
        print(f"     Got: {first_code} ({first_price:,} EGP)")
        # Check if it's still cheaper than expected (might be OK if there's another cheaper one)
        if first_price < EXPECTED_CHEAPEST['price']:
            print(f"     → Actually cheaper than expected! This might be correct.")
            checks.append(True)
        else:
            checks.append(False)
    
    # Check if results are sorted by price (ascending)
    if len(retrieved_units) > 1:
        prices = [u.get("Price") or u.get("price", 0) for u in retrieved_units]
        is_sorted = all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
        if is_sorted:
            print(f"\n  ✓ Results are sorted by price (ascending)")
            checks.append(True)
        else:
            print(f"\n  ⚠ Results are NOT sorted by price")
            checks.append(False)
    
    # Final verdict
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = all(checks)
    
    if all_passed:
        print("✅ SUCCESS: Selector correctly retrieved the cheapest apartment with sea view!")
        return True
    else:
        print("⚠ PARTIAL SUCCESS or FAILURE:")
        if is_apartment and has_sea:
            print("  ✓ Correctly filtered for apartments with sea view")
            if not is_cheapest:
                print("  ⚠ But didn't return the expected cheapest unit")
        else:
            print("  ❌ Did not correctly filter for apartments with sea view")
        return False
    
    # Show generated code
    if result.get("code"):
        print("\n" + "=" * 70)
        print("GENERATED PANDAS CODE")
        print("=" * 70)
        print(result["code"])


if __name__ == "__main__":
    success = test_cheapest_sea_apartment()
    sys.exit(0 if success else 1)

