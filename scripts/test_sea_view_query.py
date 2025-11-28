#!/usr/bin/env python3
"""
Test script to verify if the selector retrieves units with sea view (بحر)
when querying "اي الشقق اللي بتطل علي البحر"
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

# Expected units with sea view (بحر) from the CSV
EXPECTED_UNITS = {
    "Hawabay/07/B/7",      # Name 7
    "Hawabay/06/M/302",    # Name 302
    "Hawabay/06/E/1",      # Name 1
    "Hawabay/02/L/304",    # Name 304
    "Hawabay/06/B/6",      # Name 6
    "Hawabay/01/D/2",      # Name 2
}

def test_selector_query():
    """Test the selector with the sea view query."""
    
    # Check if API key is set
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Please set it in your .env file or environment")
        return False
    
    # Test query
    query = "اي الشقق اللي بتطل علي البحر"
    
    print("=" * 70)
    print("Testing Unit Selector")
    print("=" * 70)
    print(f"Query: {query}")
    print(f"Expected units with sea view (بحر): {len(EXPECTED_UNITS)} units")
    print("\nExpected unit codes:")
    for code in sorted(EXPECTED_UNITS):
        print(f"  - {code}")
    print()
    
    # Try to use the API endpoint if server is running
    api_url = "http://localhost:8000/selector/test"
    
    try:
        print("Attempting to connect to API server...")
        response = requests.post(
            api_url,
            json={
                "question": query,
                "max_rows": 20
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
            max_rows=20
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
    
    retrieved_codes = set()
    retrieved_units = result.get("units", [])
    
    if not retrieved_units:
        print("\n❌ No units retrieved!")
        print("\nGenerated code:")
        print("-" * 70)
        print(result.get("code", "No code generated"))
        print("-" * 70)
        return False
    
    print("\nRetrieved unit codes:")
    for i, unit in enumerate(retrieved_units, 1):
        code = unit.get("Code") or unit.get("code")
        name = unit.get("Name") or unit.get("name", "N/A")
        usage = unit.get("Usage") or unit.get("usage", "N/A")
        description = unit.get("Description") or unit.get("description", "")
        
        if code:
            retrieved_codes.add(code)
            has_sea = "بحر" in description or "sea view" in description.lower() or "beach view" in description.lower()
            marker = "✓" if has_sea else "?"
            print(f"  {marker} {i}. {code} (Name: {name}, Usage: {usage})")
            if has_sea:
                print(f"      → Contains 'بحر' or sea view in description")
    
    # Compare with expected
    print("\n" + "=" * 70)
    print("COMPARISON WITH EXPECTED UNITS")
    print("=" * 70)
    
    found_expected = retrieved_codes & EXPECTED_UNITS
    missing_expected = EXPECTED_UNITS - retrieved_codes
    extra_units = retrieved_codes - EXPECTED_UNITS
    
    print(f"\n✓ Found {len(found_expected)}/{len(EXPECTED_UNITS)} expected units:")
    for code in sorted(found_expected):
        print(f"  ✓ {code}")
    
    if missing_expected:
        print(f"\n❌ Missing {len(missing_expected)} expected units:")
        for code in sorted(missing_expected):
            print(f"  ❌ {code}")
    
    if extra_units:
        print(f"\n⚠ Retrieved {len(extra_units)} additional units (not in expected list):")
        for code in sorted(extra_units):
            print(f"  ⚠ {code}")
    
    # Check if all retrieved units actually have sea view
    print("\n" + "=" * 70)
    print("VERIFICATION: Do retrieved units actually have sea view?")
    print("=" * 70)
    
    all_have_sea = True
    for unit in retrieved_units:
        code = unit.get("Code") or unit.get("code", "N/A")
        description = unit.get("Description") or unit.get("description", "")
        has_sea = "بحر" in description or "sea view" in description.lower() or "beach view" in description.lower()
        
        if not has_sea:
            all_have_sea = False
            print(f"  ❌ {code}: Does NOT contain 'بحر' or sea view keywords")
        else:
            print(f"  ✓ {code}: Contains sea view keywords")
    
    # Final verdict
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    success_rate = len(found_expected) / len(EXPECTED_UNITS) if EXPECTED_UNITS else 0
    
    if success_rate == 1.0 and all_have_sea:
        print("✅ SUCCESS: All expected units retrieved and all have sea view!")
        return True
    elif success_rate >= 0.5:
        print(f"⚠ PARTIAL SUCCESS: Found {len(found_expected)}/{len(EXPECTED_UNITS)} expected units ({success_rate*100:.0f}%)")
        if not all_have_sea:
            print("⚠ Warning: Some retrieved units don't have sea view keywords")
        return True
    else:
        print(f"❌ FAILED: Only found {len(found_expected)}/{len(EXPECTED_UNITS)} expected units ({success_rate*100:.0f}%)")
        return False
    
    # Show generated code
    if result.get("code"):
        print("\n" + "=" * 70)
        print("GENERATED PANDAS CODE")
        print("=" * 70)
        print(result["code"])


if __name__ == "__main__":
    success = test_selector_query()
    sys.exit(0 if success else 1)

