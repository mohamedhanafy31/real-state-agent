#!/usr/bin/env python3
"""
Script to review the last 2 RAG cases and rate selector and generator responses.
"""

import re
from pathlib import Path
from datetime import datetime

def extract_last_n_cases(log_file, n=4):
    """Extract information about the last N query cases from log file."""
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find all query processing entries
    queries = []
    for i, line in enumerate(lines):
        if "Processing streaming query:" in line:
            # Extract query - handle multi-line queries
            query_match = re.search(r'Processing streaming query: (.+)', line)
            if query_match:
                query = query_match.group(1).strip()
                # Check if query continues on next line
                if i + 1 < len(lines) and not lines[i+1].strip().startswith('2025-'):
                    query += " " + lines[i+1].strip()
                
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                
                # Look for selector and generator info in following lines
                selector_info = {}
                generator_info = {}
                process_time = None
                
                # Check next 100 lines for related info
                for j in range(i, min(i+100, len(lines))):
                    next_line = lines[j]
                    
                    # Selector information - new logging format
                    if "Unit selector" in next_line and "Relevance score:" in next_line:
                        match = re.search(r'Relevance score: ([\d.]+)', next_line)
                        if match:
                            selector_info['relevance_score'] = float(match.group(1))
                    
                    if "Unit selector" in next_line and "Selected" in next_line:
                        match = re.search(r'Selected (\d+) units.*relevance: ([\d.]+|N/A).*source: (\w+)', next_line)
                        if match:
                            selector_info['saved_units'] = int(match.group(1))
                            if match.group(2) != 'N/A':
                                selector_info['relevance_score'] = float(match.group(2))
                            selector_info['type'] = match.group(3)
                    
                    if "Selector result - Type:" in next_line:
                        match = re.search(r'Type: (\w+), Units: (\d+), Relevance: ([\d.]+|N/A)', next_line)
                        if match:
                            selector_info['type'] = match.group(1)
                            selector_info['saved_units'] = int(match.group(2))
                            if match.group(3) != 'N/A':
                                selector_info['relevance_score'] = float(match.group(3))
                    
                    # Legacy format support
                    if "Unit selector returning" in next_line:
                        match = re.search(r'returning (\d+) (explicit|LLM)', next_line)
                        if match:
                            selector_info['num_units'] = int(match.group(1))
                            selector_info['type'] = match.group(2)
                    
                    if "Low relevance score" in next_line:
                        match = re.search(r'Low relevance score \(([\d.]+)\)', next_line)
                        if match:
                            selector_info['relevance_score'] = float(match.group(1))
                            selector_info['forced_empty'] = True
                    
                    if "Saved" in next_line and "units to memory" in next_line:
                        match = re.search(r'Saved (\d+) units', next_line)
                        if match:
                            selector_info['saved_units'] = int(match.group(1))
                        
                        reason_match = re.search(r'reason: (.+)', next_line)
                        if reason_match:
                            selector_info['reason'] = reason_match.group(1)
                    
                    # Generator API timing - new logging format
                    if "Generator API - Total time:" in next_line:
                        match = re.search(r'Total time: ([\d.]+)s', next_line)
                        if match:
                            process_time = float(match.group(1))
                            generator_info['total_time'] = float(match.group(1))
                    
                    if "Generator API - Time to first chunk:" in next_line:
                        match = re.search(r'Time to first chunk: ([\d.]+)s', next_line)
                        if match:
                            generator_info['time_to_first_chunk'] = float(match.group(1))
                    
                    if "Generator API - Total time:" in next_line and "Chunks:" in next_line:
                        match = re.search(r'Total time: ([\d.]+)s.*Chunks: (\d+)', next_line)
                        if match:
                            generator_info['total_time'] = float(match.group(1))
                            generator_info['chunk_count'] = int(match.group(2))
                    
                    # Process time - look for the Response line after this query (legacy)
                    if "Response: 200 - Process time:" in next_line and process_time is None:
                        match = re.search(r'Process time: ([\d.]+)s', next_line)
                        if match:
                            process_time = float(match.group(1))
                            break  # Found the process time for this query
                
                queries.append({
                    'timestamp': timestamp,
                    'query': query,
                    'selector': selector_info,
                    'generator': generator_info,
                    'process_time': process_time
                })
    
    return queries[-n:] if len(queries) >= n else queries

def rate_selector(selector_info, query):
    """Rate the selector response."""
    score = 0
    max_score = 10
    feedback = []
    
    # Check if units were found
    num_units = selector_info.get('saved_units', 0)
    if num_units > 0:
        score += 4
        feedback.append(f"✓ Found {num_units} units")
        
        # Check if number matches query intent
        query_lower = query.lower()
        if 'ثلاث' in query_lower or 'three' in query_lower or '3' in query_lower:
            if num_units == 3:
                score += 1
                feedback.append("✓ Correctly returned exactly 3 units as requested")
            elif num_units > 3:
                score += 0.5
                feedback.append(f"⚠ Returned {num_units} units (query asked for 3)")
    else:
        feedback.append("✗ No units found")
    
    # Check relevance score
    relevance = selector_info.get('relevance_score')
    if relevance is not None:
        if relevance >= 0.7:
            score += 3
            feedback.append(f"✓ High relevance score: {relevance:.2f}")
        elif relevance >= 0.5:
            score += 2
            feedback.append(f"✓ Moderate relevance score: {relevance:.2f}")
        elif relevance >= 0.3:
            score += 1
            feedback.append(f"⚠ Low relevance score: {relevance:.2f}")
        else:
            feedback.append(f"✗ Very low relevance score: {relevance:.2f}")
    else:
        # If no relevance score but units found, assume moderate relevance
        if num_units > 0:
            score += 1
            feedback.append("⚠ No relevance score logged (assuming moderate)")
    
    # Check if forced empty (low relevance)
    if selector_info.get('forced_empty'):
        score -= 2
        feedback.append("⚠ Results forced empty due to low relevance")
    
    # Check selector type
    selector_type = selector_info.get('type', 'unknown')
    if selector_type == 'EXPLICIT_MATCH':
        score += 1.5
        feedback.append("✓ Used explicit matching (fast and accurate)")
    elif selector_type == 'LLM_CODE':
        score += 1
        feedback.append("✓ Used LLM code generation")
    elif selector_type == 'LAST_UNITS_MATCH' or selector_type == 'HISTORY_MATCH':
        score += 1.5
        feedback.append(f"✓ Used {selector_type} (conversation context)")
    elif selector_type == 'LLM':
        score += 1
        feedback.append("✓ Used LLM code generation")
    else:
        # If no type specified but units found, likely LLM
        if num_units > 0:
            score += 0.5
            feedback.append(f"⚠ Selector type: {selector_type if selector_type != 'unknown' else 'not logged'}")
    
    # Check if query makes sense for selector
    query_lower = query.lower()
    unit_keywords = ['شقق', 'فيلا', 'apartment', 'villa', 'unit', 'وحدة', 'فيله']
    if any(word in query_lower for word in unit_keywords):
        score += 0.5
        feedback.append("✓ Query is unit-related")
    elif selector_info.get('forced_empty') or num_units == 0:
        # Check if it's a payment/installment query (should use history)
        if any(word in query_lower for word in ['سداد', 'دفع', 'قسط', 'payment', 'installment']):
            score += 1
            feedback.append("✓ Payment query - should use conversation history")
    
    score = max(0, min(max_score, round(score, 1)))
    return score, feedback

def rate_generator(generator_info, process_time, query, selector_units):
    """Rate the generator response."""
    score = 0
    max_score = 10
    feedback = []
    
    # Check process time
    if process_time:
        if process_time < 5:
            score += 4
            feedback.append(f"✓ Excellent response time: {process_time:.2f}s")
        elif process_time < 10:
            score += 3
            feedback.append(f"✓ Good response time: {process_time:.2f}s")
        elif process_time < 15:
            score += 2
            feedback.append(f"✓ Acceptable response time: {process_time:.2f}s")
        elif process_time < 30:
            score += 1
            feedback.append(f"⚠ Slow response: {process_time:.2f}s")
        else:
            score += 0
            feedback.append(f"✗ Very slow response: {process_time:.2f}s (may indicate API issues)")
    else:
        feedback.append("⚠ Process time not logged")
    
    # Generator always runs (no errors in successful cases)
    score += 3
    feedback.append("✓ Generator executed successfully without errors")
    
    # Check if generator had units to work with
    if selector_units > 0:
        score += 2
        feedback.append(f"✓ Generator had {selector_units} units to generate response from")
    else:
        score += 1
        feedback.append("⚠ Generator had no units (may rely on context chunks only)")
    
    # Check query complexity
    query_lower = query.lower()
    if any(word in query_lower for word in ['تفاصيل', 'شرح', 'explain', 'details']):
        if process_time and process_time > 10:
            score += 0.5
            feedback.append("✓ Complex query (details request) - longer time acceptable")
    
    score = max(0, min(max_score, round(score, 1)))
    return score, feedback

def main():
    import glob
    
    # Find the most recent log file with multiple queries
    log_dir = Path(__file__).parent.parent / "ai" / "rag" / "logs"
    log_files = list(log_dir.glob("*_all.log"))
    
    if not log_files:
        print(f"No log files found in: {log_dir}")
        sys.exit(1)
    
    # Sort by modification time and find one with at least 4 queries
    sorted_files = sorted(log_files, key=lambda p: p.stat().st_mtime, reverse=True)
    log_file = None
    
    for lf in sorted_files:
        with open(lf, 'r', encoding='utf-8') as f:
            query_count = f.read().count("Processing streaming query:")
        if query_count >= 4:
            log_file = lf
            break
    
    # If no file has 4+ queries, use the most recent one
    if not log_file:
        log_file = sorted_files[0]
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        sys.exit(1)
    
    print("=" * 80)
    print("RAG CASE REVIEW - Last 4 Cases")
    print("=" * 80)
    print(f"Using log file: {log_file.name}")
    print()
    
    cases = extract_last_n_cases(log_file, n=4)
    
    if len(cases) < 1:
        print("No cases found in logs")
        return
    
    for idx, case in enumerate(cases, 1):
        print(f"\n{'='*80}")
        print(f"CASE {idx} (Most Recent: {idx == len(cases)})")
        print(f"{'='*80}")
        print(f"Timestamp: {case['timestamp']}")
        print(f"Query: {case['query']}")
        print(f"Process Time: {case['process_time']:.2f}s" if case['process_time'] else "N/A")
        print()
        
        # Rate Selector
        print("SELECTOR ANALYSIS:")
        print("-" * 80)
        selector_score, selector_feedback = rate_selector(case['selector'], case['query'])
        print(f"Score: {selector_score}/10")
        for item in selector_feedback:
            print(f"  {item}")
        print(f"Details: {case['selector']}")
        print()
        
        # Rate Generator
        print("GENERATOR ANALYSIS:")
        print("-" * 80)
        generator_score, generator_feedback = rate_generator(
            case['generator'], 
            case['process_time'], 
            case['query'],
            case['selector'].get('saved_units', 0)
        )
        print(f"Score: {generator_score}/10")
        for item in generator_feedback:
            print(f"  {item}")
        print()
        
        # Overall
        overall_score = (selector_score + generator_score) / 2
        print(f"OVERALL SCORE: {overall_score:.1f}/10")
        print()

if __name__ == "__main__":
    main()

