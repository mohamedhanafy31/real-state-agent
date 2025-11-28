#!/usr/bin/env python3
"""
Detailed review of selector result for the last case.
"""

import re
from pathlib import Path
import sys

def analyze_last_case():
    """Analyze the last case in detail."""
    log_dir = Path(__file__).parent.parent / "ai" / "rag" / "logs"
    log_files = list(log_dir.glob("*_all.log"))
    
    if not log_files:
        print("No log files found")
        return
    
    log_file = max(log_files, key=lambda p: p.stat().st_mtime)
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the last query
    last_query_line = None
    last_query_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if "Processing streaming query:" in lines[i]:
            last_query_line = lines[i]
            last_query_idx = i
            break
    
    if not last_query_line:
        print("No query found in logs")
        return
    
    # Extract query
    query_match = re.search(r'Processing streaming query: (.+)', last_query_line)
    if not query_match:
        print("Could not extract query")
        return
    
    query = query_match.group(1).strip()
    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', last_query_line)
    timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
    
    print("=" * 80)
    print("SELECTOR RESULT REVIEW - Last Case")
    print("=" * 80)
    print(f"Timestamp: {timestamp}")
    print(f"Query: {query}")
    print()
    
    # Extract selector information
    selector_info = {}
    for i in range(last_query_idx, min(last_query_idx + 50, len(lines))):
        line = lines[i]
        
        if "Extracted" in line and "units from additional message" in line:
            match = re.search(r'Extracted (\d+) units from additional message: \[(.+)\]', line)
            if match:
                selector_info['additional_units_extracted'] = int(match.group(1))
                selector_info['additional_units_list'] = match.group(2)
                print(f"✓ Additional units extracted: {match.group(2)}")
        
        if "EXPLICIT_MATCH" in line and "additional message" in line:
            match = re.search(r'Matched (\d+) units', line)
            if match:
                selector_info['explicit_match_success'] = True
                selector_info['explicit_match_count'] = int(match.group(1))
                print(f"✓ EXPLICIT_MATCH succeeded: {match.group(1)} units")
                break
        
        if "Could not match units from additional message" in line:
            selector_info['explicit_match_failed'] = True
            print("✗ EXPLICIT_MATCH failed - Could not match units from additional message")
        
        if "Unit selector LLM_CODE - Relevance score:" in line:
            match = re.search(r'Relevance score: ([\d.]+)', line)
            if match:
                selector_info['relevance_score'] = float(match.group(1))
                print(f"Relevance score: {match.group(1)}")
        
        if "Unit selector LLM_CODE - Selected" in line:
            match = re.search(r'Selected (\d+) units', line)
            if match:
                selector_info['final_units'] = int(match.group(1))
                print(f"Final result: {match.group(1)} units selected")
        
        if "Selector result - Type:" in line:
            match = re.search(r'Type: (\w+), Units: (\d+), Relevance: ([\d.]+|N/A)', line)
            if match:
                selector_info['final_type'] = match.group(1)
                selector_info['final_units'] = int(match.group(2))
                selector_info['final_relevance'] = match.group(3)
    
    print()
    print("=" * 80)
    print("ANALYSIS:")
    print("=" * 80)
    
    if selector_info.get('additional_units_extracted'):
        print(f"✓ Additional message was parsed: {selector_info.get('additional_units_list')}")
        
        if selector_info.get('explicit_match_success'):
            print("✓ EXPLICIT_MATCH worked correctly")
        elif selector_info.get('explicit_match_failed'):
            print("✗ EXPLICIT_MATCH failed - Unit IDs from additional message were not found")
            print("  Possible reasons:")
            print("  - Unit ID format mismatch (e.g., '203' vs 'Hawabay/27/I/203')")
            print("  - Unit ID not in CSV data")
            print("  - Matching logic needs improvement")
        else:
            print("⚠ EXPLICIT_MATCH was not attempted or logged")
    
    if selector_info.get('final_units') == 0:
        print("\n✗ ISSUE: No units were selected in the final result")
        print("  This means the query could not be answered with unit data")
        
        if selector_info.get('relevance_score'):
            rel_score = selector_info['relevance_score']
            if rel_score >= 0.7:
                print(f"  ⚠ High relevance ({rel_score}) but no units found - this is unusual")
                print("  Possible reasons:")
                print("  - LLM generated code that didn't match any units")
                print("  - Query was about payment/installment which requires specific unit context")
            elif rel_score >= 0.5:
                print(f"  ⚠ Moderate relevance ({rel_score}) - query partially matches CSV structure")
            else:
                print(f"  ✓ Low relevance ({rel_score}) - query doesn't match CSV data (expected)")
    
    print()
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if selector_info.get('additional_units_extracted') and not selector_info.get('explicit_match_success'):
        print("1. Fix EXPLICIT_MATCH logic to handle unit IDs from additional message")
        print("   - Ensure standalone numbers like '203' can match Name column or Code endings")
        print("   - Add better logging to see why matching failed")
    
    if selector_info.get('final_units') == 0 and selector_info.get('relevance_score', 0) >= 0.7:
        print("2. Investigate why high-relevance queries return 0 units")
        print("   - Check if LLM-generated code is correct")
        print("   - Verify CSV data contains matching units")
        print("   - Consider adding fallback to conversation history when relevance is high")

if __name__ == "__main__":
    analyze_last_case()

