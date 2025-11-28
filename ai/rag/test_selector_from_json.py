#!/usr/bin/env python3
"""
Test script for UnitSelector component based on testSelector.json
Tests the selector with queries from JSON file and validates results.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Import directly from selector to avoid importing full RAG pipeline (which requires torch)
from src.selector.unit_selector import UnitSelector, UnitSelectorResult
from src.utils import setup_run_logging, get_logger
import pandas as pd

# Setup logging
run_logger = setup_run_logging(
    run_name=f"test_selector_json_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    log_dir=os.getenv('LOG_DIR', 'logs'),
    level=os.getenv('LOG_LEVEL', 'INFO'),
    console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
    file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
)

logger = get_logger(__name__)


def load_test_cases(json_path: str) -> Dict[str, Any]:
    """Load test cases from JSON file."""
    json_file = Path(json_path)
    if not json_file.exists():
        raise FileNotFoundError(f"Test cases file not found: {json_path}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Loaded {len(data.get('examples', []))} test cases from {json_path}")
    return data


def load_csv_reference(csv_path: str) -> pd.DataFrame:
    """Load CSV file for reference (to map row indices to actual data)."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_file)
    logger.info(f"Loaded CSV reference with {len(df)} rows")
    return df


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_result(example_idx: int, example: Dict[str, Any], result: UnitSelectorResult,
                 csv_df: pd.DataFrame = None, expected_rows: List[int] = None):
    """Print formatted test result."""
    print_separator("-")
    print(f"\n[Example {example_idx + 1}]")
    print(f"Query: {example['query']}")
    print(f"Description: {example.get('description', 'N/A')}")
    print(f"Expected Filter: {example.get('expected_filter', 'N/A')}")
    
    if expected_rows:
        print(f"Expected Row Indices: {expected_rows}")
    
    print(f"\nStatus: {'✓ SUCCESS' if result.success else '✗ FAILED'}")
    
    if result.relevance_score is not None:
        score_percent = result.relevance_score * 100
        print(f"Relevance Score: {result.relevance_score:.2f} ({score_percent:.1f}%)")
    
    if result.error:
        print(f"Error: {result.error}")
    
    print(f"\nGenerated Code:")
    print("-" * 80)
    if result.code:
        for i, line in enumerate(result.code.split('\n'), 1):
            print(f"{i:3d} | {line}")
    else:
        print("(No code generated)")
    
    print(f"\nResults: {len(result.rows)} units found")
    
    if result.rows:
        print("\nMatching Units:")
        print("-" * 80)
        for idx, row in enumerate(result.rows[:10], 1):  # Show first 10
            code = row.get('Code', 'N/A')
            price = row.get('Price', 'N/A')
            area = row.get('Area', 'N/A')
            usage = row.get('Usage', 'N/A')
            floor = row.get('Floor', 'N/A')
            garden = row.get('Garden', 'N/A')
            building = row.get('Building', 'N/A')
            
            print(f"\n  Unit {idx}:")
            print(f"    Code: {code}")
            print(f"    Price: {price:,} EGP" if isinstance(price, (int, float)) else f"    Price: {price}")
            print(f"    Area: {area} m²" if isinstance(area, (int, float)) else f"    Area: {area}")
            print(f"    Usage: {usage}")
            print(f"    Floor: {floor}")
            print(f"    Building: {building}")
            if garden and garden != 0:
                print(f"    Garden: {garden} m²" if isinstance(garden, (int, float)) else f"    Garden: {garden}")
        
        if len(result.rows) > 10:
            print(f"\n  ... and {len(result.rows) - 10} more units")
        
        # Try to match with expected rows if CSV reference is available
        if csv_df is not None and expected_rows:
            print(f"\nValidation:")
            print("-" * 80)
            matched_codes = {row.get('Code') for row in result.rows}
            expected_codes = set()
            for row_idx in expected_rows:
                if 0 <= row_idx - 1 < len(csv_df):  # Convert to 0-based index
                    expected_codes.add(csv_df.iloc[row_idx - 1].get('Code', ''))
            
            if expected_codes:
                matched = matched_codes.intersection(expected_codes)
                missing = expected_codes - matched_codes
                extra = matched_codes - expected_codes
                
                print(f"  Expected codes: {sorted(expected_codes)}")
                print(f"  Found codes: {sorted(matched_codes)}")
                print(f"  ✓ Matched: {len(matched)}/{len(expected_codes)} - {sorted(matched) if matched else 'None'}")
                if missing:
                    print(f"  ✗ Missing: {sorted(missing)}")
                if extra:
                    print(f"  ⚠ Extra: {sorted(extra)}")
    else:
        print("(No units matched)")
    
    print()


def test_selector(selector: UnitSelector, examples: List[Dict[str, Any]], 
                 csv_df: pd.DataFrame = None) -> Dict[str, Any]:
    """Test selector with all examples and return statistics."""
    results = []
    stats = {
        'total': len(examples),
        'successful': 0,
        'failed': 0,
        'total_units_found': 0,
        'questions_with_results': 0,
        'questions_without_results': 0,
        'errors': []
    }
    
    print_separator("=")
    print("UNIT SELECTOR TEST RESULTS (from testSelector.json)")
    print_separator("=")
    print(f"Testing {stats['total']} examples...\n")
    
    for i, example in enumerate(examples):
        query = example['query']
        expected_rows = example.get('returned_rows', [])
        
        try:
            logger.info(f"Testing example {i+1}: {query}")
            result = selector.select_units(query)
            
            results.append({
                'example_idx': i,
                'example': example,
                'result': result,
            })
            
            if result.success:
                stats['successful'] += 1
                stats['total_units_found'] += len(result.rows)
                if result.rows:
                    stats['questions_with_results'] += 1
                else:
                    stats['questions_without_results'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append({
                    'example_idx': i,
                    'query': query,
                    'error': result.error
                })
            
            # Print result
            print_result(
                i,
                example,
                result,
                csv_df,
                expected_rows
            )
            
        except Exception as e:
            logger.error(f"Exception testing example {i+1}: {str(e)}", exc_info=True)
            stats['failed'] += 1
            stats['errors'].append({
                'example_idx': i,
                'query': query,
                'error': f"Exception: {str(e)}"
            })
            print(f"\n[Example {i+1}] Exception: {str(e)}\n")
    
    return {
        'results': results,
        'stats': stats
    }


def print_summary(stats: Dict[str, Any]):
    """Print test summary statistics."""
    print_separator("=")
    print("TEST SUMMARY")
    print_separator("=")
    
    print(f"\nTotal Examples: {stats['total']}")
    print(f"Successful: {stats['successful']} ({stats['successful']/stats['total']*100:.1f}%)")
    print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"\nTotal Units Found: {stats['total_units_found']}")
    print(f"Examples with Results: {stats['questions_with_results']}")
    print(f"Examples without Results: {stats['questions_without_results']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        print("-" * 80)
        for error in stats['errors']:
            print(f"  Example {error['example_idx']+1}: {error['query']}")
            print(f"    Error: {error['error']}\n")
    
    print_separator("=")


def main():
    """Main test function."""
    print("=" * 80)
    print("UnitSelector Test Script (from testSelector.json)")
    print("=" * 80)
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("\n❌ ERROR: GEMINI_API_KEY environment variable not set!")
        print("Set it with: export GEMINI_API_KEY='your-api-key'")
        print("Or add it to your .env file")
        return 1
    
    # Load test cases
    test_json_path = project_root / "data" / "testSelector.json"
    if not test_json_path.exists():
        # Try alternative path
        test_json_path = project_root.parent.parent / "data" / "testSelector.json"
        if not test_json_path.exists():
            print(f"\n❌ ERROR: Test cases file not found at {test_json_path}")
            return 1
    
    try:
        test_data = load_test_cases(str(test_json_path))
        examples = test_data.get('examples', [])
        if not examples:
            print("\n❌ ERROR: No examples found in test cases file")
            return 1
    except Exception as e:
        logger.error(f"Failed to load test cases: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: Failed to load test cases: {str(e)}")
        return 1
    
    # Get CSV path
    csv_path = project_root / "data" / "11-15_sample25.csv"
    if not csv_path.exists():
        # Try alternative path
        csv_path = project_root.parent.parent / "data" / "11-15_sample25.csv"
        if not csv_path.exists():
            print(f"\n❌ ERROR: CSV file not found at {csv_path}")
            return 1
    
    # Load CSV reference for validation
    csv_df = None
    try:
        csv_df = load_csv_reference(str(csv_path))
    except Exception as e:
        logger.warning(f"Could not load CSV reference: {e}")
        print(f"⚠ Warning: Could not load CSV reference for validation: {e}")
    
    print(f"\nTest Cases File: {test_json_path}")
    print(f"CSV Path: {csv_path}")
    print(f"API Key: {'✓ Set' if api_key else '✗ Not set'}\n")
    
    # Initialize selector
    try:
        print("Initializing UnitSelector...")
        selector = UnitSelector(
            csv_path=str(csv_path),
            api_key=api_key,
            model_name="gemini-2.0-flash",
            max_rows=10  # Limit to 10 units per query
        )
        print("✓ UnitSelector initialized successfully\n")
    except Exception as e:
        logger.error(f"Failed to initialize UnitSelector: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: Failed to initialize UnitSelector: {str(e)}")
        return 1
    
    # Run tests
    try:
        test_results = test_selector(selector, examples, csv_df)
        print_summary(test_results['stats'])
        
        # Save detailed results to JSON in data/ directory
        output_file = project_root / "data" / f"selector_test_json_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        # Prepare results for JSON serialization
        json_results = {
            'timestamp': datetime.now().isoformat(),
            'test_file': str(test_json_path),
            'csv_file': str(csv_path),
            'stats': test_results['stats'],
            'results': []
        }
        
        for r in test_results['results']:
            json_results['results'].append({
                'example_idx': r['example_idx'],
                'query': r['example'].get('query'),
                'description': r['example'].get('description'),
                'expected_filter': r['example'].get('expected_filter'),
                'expected_rows': r['example'].get('returned_rows', []),
                'success': r['result'].success,
                'error': r['result'].error,
                'code': r['result'].code,
                'num_units': len(r['result'].rows),
                'relevance_score': r['result'].relevance_score,
                'units': r['result'].rows[:10]  # Save first 10 units
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Detailed results saved to: {output_file}")
        
        return 0 if test_results['stats']['failed'] == 0 else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
