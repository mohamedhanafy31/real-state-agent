#!/usr/bin/env python3
"""
Test script for UnitSelector component.
Tests the selector with Egyptian dialect questions from JSON file.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

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

from src.selector import UnitSelector, UnitSelectorResult
from src.utils import setup_run_logging, get_logger

# Setup logging
run_logger = setup_run_logging(
    run_name=f"test_selector_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    log_dir=os.getenv('LOG_DIR', 'logs'),
    level=os.getenv('LOG_LEVEL', 'INFO'),
    console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
    file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG')
)

logger = get_logger(__name__)


def load_test_questions(json_path: str) -> Dict[str, Any]:
    """Load test questions from JSON file."""
    json_file = Path(json_path)
    if not json_file.exists():
        raise FileNotFoundError(f"Test questions file not found: {json_path}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Loaded {len(data['test_questions'])} test questions from {json_path}")
    return data


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_result(question_id: int, question: str, result: UnitSelectorResult, 
                 expected_filters: List[str] = None):
    """Print formatted test result."""
    print_separator("-")
    print(f"\n[Question {question_id}]")
    print(f"Question: {question}")
    
    if expected_filters:
        print(f"Expected filters: {', '.join(expected_filters)}")
    
    print(f"\nStatus: {'✓ SUCCESS' if result.success else '✗ FAILED'}")
    
    if result.error:
        print(f"Error: {result.error}")
    
    print(f"\nGenerated Code:")
    print("-" * 80)
    if result.code:
        # Print code with syntax highlighting (basic)
        for i, line in enumerate(result.code.split('\n'), 1):
            print(f"{i:3d} | {line}")
    else:
        print("(No code generated)")
    
    print(f"\nResults: {len(result.rows)} units found")
    
    if result.rows:
        print("\nMatching Units:")
        print("-" * 80)
        for idx, row in enumerate(result.rows[:5], 1):  # Show first 5
            code = row.get('Code', 'N/A')
            price = row.get('Price', 'N/A')
            area = row.get('Area', 'N/A')
            usage = row.get('Usage', 'N/A')
            floor = row.get('Floor', 'N/A')
            garden = row.get('Garden', 'N/A')
            
            print(f"\n  Unit {idx}:")
            print(f"    Code: {code}")
            print(f"    Price: {price:,} EGP" if isinstance(price, (int, float)) else f"    Price: {price}")
            print(f"    Area: {area} m²" if isinstance(area, (int, float)) else f"    Area: {area}")
            print(f"    Usage: {usage}")
            print(f"    Floor: {floor}")
            if garden and garden != 0:
                print(f"    Garden: {garden} m²" if isinstance(garden, (int, float)) else f"    Garden: {garden}")
        
        if len(result.rows) > 5:
            print(f"\n  ... and {len(result.rows) - 5} more units")
    else:
        print("(No units matched)")
    
    if result.raw_response and result.raw_response != result.code:
        print(f"\nRaw LLM Response (first 200 chars):")
        print("-" * 80)
        print(result.raw_response[:200] + "..." if len(result.raw_response) > 200 else result.raw_response)
    
    print()


def test_selector(selector: UnitSelector, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test selector with all questions and return statistics."""
    results = []
    stats = {
        'total': len(questions),
        'successful': 0,
        'failed': 0,
        'total_units_found': 0,
        'questions_with_results': 0,
        'questions_without_results': 0,
        'errors': []
    }
    
    print_separator("=")
    print("UNIT SELECTOR TEST RESULTS")
    print_separator("=")
    print(f"Testing {stats['total']} questions...\n")
    
    for i, q_data in enumerate(questions, 1):
        question = q_data['question']
        expected_filters = q_data.get('expected_filters', [])
        
        try:
            logger.info(f"Testing question {i}: {question}")
            result = selector.select_units(question)
            
            results.append({
                'question_id': q_data['id'],
                'question': question,
                'result': result,
                'expected_filters': expected_filters
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
                    'question_id': q_data['id'],
                    'question': question,
                    'error': result.error
                })
            
            # Print result
            print_result(
                q_data['id'],
                question,
                result,
                expected_filters
            )
            
        except Exception as e:
            logger.error(f"Exception testing question {i}: {str(e)}", exc_info=True)
            stats['failed'] += 1
            stats['errors'].append({
                'question_id': q_data['id'],
                'question': question,
                'error': f"Exception: {str(e)}"
            })
            print(f"\n[Question {q_data['id']}] Exception: {str(e)}\n")
    
    return {
        'results': results,
        'stats': stats
    }


def print_summary(stats: Dict[str, Any]):
    """Print test summary statistics."""
    print_separator("=")
    print("TEST SUMMARY")
    print_separator("=")
    
    print(f"\nTotal Questions: {stats['total']}")
    print(f"Successful: {stats['successful']} ({stats['successful']/stats['total']*100:.1f}%)")
    print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"\nTotal Units Found: {stats['total_units_found']}")
    print(f"Questions with Results: {stats['questions_with_results']}")
    print(f"Questions without Results: {stats['questions_without_results']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        print("-" * 80)
        for error in stats['errors']:
            print(f"  Q{error['question_id']}: {error['question']}")
            print(f"    Error: {error['error']}\n")
    
    print_separator("=")


def main():
    """Main test function."""
    print("=" * 80)
    print("UnitSelector Test Script")
    print("=" * 80)
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("\n❌ ERROR: GEMINI_API_KEY environment variable not set!")
        print("Set it with: export GEMINI_API_KEY='your-api-key'")
        print("Or add it to your .env file")
        return 1
    
    # Load test questions
    questions_file = project_root / "test_selector_questions.json"
    try:
        test_data = load_test_questions(str(questions_file))
        questions = test_data['test_questions']
    except Exception as e:
        logger.error(f"Failed to load test questions: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: Failed to load test questions: {str(e)}")
        return 1
    
    # Get CSV path
    csv_path = project_root / "data" / "11-15_sample25.csv"
    if not csv_path.exists():
        # Try alternative path
        csv_path = project_root.parent.parent / "data" / "11-15_sample25.csv"
        if not csv_path.exists():
            print(f"\n❌ ERROR: CSV file not found at {csv_path}")
            return 1
    
    print(f"\nCSV Path: {csv_path}")
    print(f"Questions File: {questions_file}")
    print(f"API Key: {'✓ Set' if api_key else '✗ Not set'}\n")
    
    # Initialize selector
    try:
        print("Initializing UnitSelector...")
        selector = UnitSelector(
            csv_path=str(csv_path),
            api_key=api_key,
            model_name="gemini-2.0-flash",
            max_rows=10
        )
        print("✓ UnitSelector initialized successfully\n")
    except Exception as e:
        logger.error(f"Failed to initialize UnitSelector: {str(e)}", exc_info=True)
        print(f"\n❌ ERROR: Failed to initialize UnitSelector: {str(e)}")
        return 1
    
    # Run tests
    try:
        test_results = test_selector(selector, questions)
        print_summary(test_results['stats'])
        
        # Save detailed results to JSON
        output_file = project_root / "logs" / f"selector_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        # Prepare results for JSON serialization
        json_results = {
            'timestamp': datetime.now().isoformat(),
            'stats': test_results['stats'],
            'results': []
        }
        
        for r in test_results['results']:
            json_results['results'].append({
                'question_id': r['question_id'],
                'question': r['question'],
                'expected_filters': r['expected_filters'],
                'success': r['result'].success,
                'error': r['result'].error,
                'code': r['result'].code,
                'num_units': len(r['result'].rows),
                'units': r['result'].rows[:5]  # Save first 5 units
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

