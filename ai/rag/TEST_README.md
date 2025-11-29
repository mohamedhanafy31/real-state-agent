# Broker Behavior Test Suite

Automated testing framework for the real estate chatbot's broker behavior.

## Overview

This test suite executes **30 test cases** (15 conversational + 15 single-query) against the RAG API to validate:
- **Generator**: Professional tone, description extraction, payment calculations
- **Selector**: Multi-filter queries, sorting, unit code lookups
- **RAG System**: Context memory, developer profile retrieval, amenities

## Prerequisites

```bash
pip install requests
```

## Usage

### Run All Tests

```bash
python test_broker_behavior.py
```

### Run Against Local RAG API

```bash
python test_broker_behavior.py http://localhost:8000
```

### Run Against Production

```bash
python test_broker_behavior.py https://rag-api-dbgj63mjca-uc.a.run.app
```

## Test Cases Implemented

### Conversational Tests (3 included, expand to 15)
1. **First-Time Buyer Journey** (7 queries)
   - Greeting → Price inquiry → Budget filter → Cheapest 3 → Specific unit → Payment → Booking

2. **Sea View Preference** (7 queries)
   - Sea view request → Count → Most expensive → Cheapest → Comparison → Code lookup → Contact

3. **Villa with Garden** (7 queries)
   - Villa request → Garden inquiry → Size → Price → Cheaper option → Payment plan → Developer info

### Single-Query Tests (7 included, expand to 15)
16. Cheapest Unit Query
17. Most Expensive Unit
18. Total Units Available
20. Specific Unit Code (Hawabay/02/D/1)
24. Building Query (05/M)
25. Third Floor Units
29. Security Features

## Output

### Console Output
```
================================================================================
Test 1: First-Time Buyer Journey
Scenario: New customer exploring options
================================================================================

Query 1/7: السلام عليكم، عايز أعرف عن الوحدات المتاحة
  ✅ PASS (1.23s)
  Response: مرحباً! عندنا مجموعة متنوعة من الوحدات في كمباوند هاواي باي...

Query 2/7: ايه أسعار الشقق عندكم؟
  ✅ PASS (1.45s)
  Units: Hawabay/27/I/202, Hawabay/05/M/301, Hawabay/02/L/1
  Response: أسعار الشقق تبدأ من 4 مليون جنيه...
```

### Test Report (JSON)
```json
{
  "test_id": 1,
  "test_name": "First-Time Buyer Journey",
  "query": "السلام عليكم، عايز أعرف عن الوحدات المتاحة",
  "passed": true,
  "response": "مرحباً! عندنا مجموعة متنوعة...",
  "units_returned": ["Hawabay/27/I/202", "Hawabay/05/M/301"],
  "elapsed_time": 1.23,
  "issues": []
}
```

Saved to: `test_report_YYYYMMDD_HHMMSS.json`

### Summary Report
```
================================================================================
TEST REPORT
================================================================================

Total Queries: 50
Passed: 47 (94.0%)
Failed: 3 (6.0%)
Average Response Time: 1.42s

Test Name                                          Pass   Fail  
-----------------------------------------------------------------
First-Time Buyer Journey                           7      0     
Sea View Preference                                6      1     
Villa with Garden                                  7      0     
...
```

## Validation Criteria

Each test query validates:
- ✅ **Response Presence**: Non-empty answer
- ✅ **Expected Keywords**: Key terms in response (e.g., "sea view", "مقدم", "villa")
- ✅ **Expected Units**: Correct unit codes returned in metadata
- ✅ **Price Range**: Units within specified price bounds
- ✅ **Response Time**: Tracked for performance monitoring

## Extending Tests

### Add New Conversational Test

```python
test_cases.append(TestCase(
    id=4,
    name="Payment Plan Exploration",
    scenario="Customer exploring financing options",
    queries=[
        TestQuery("نظام السداد عندكم ازاي؟", expected_keywords=["مقدم", "10%"]),
        TestQuery("المقدم كام في المية؟", expected_keywords=["10"]),
        TestQuery("والباقي بيتقسم ازاي؟", expected_keywords=["قسط", "سنين"]),
        TestQuery("في خيارات أقساط؟", expected_keywords=["4 سنين", "5 سنين"]),
    ]
))
```

### Add New Single-Query Test

```python
test_cases.append(TestCase(
    id=21,
    name="Average Price Query",
    scenario="Query average price",
    queries=[
        TestQuery(
            "متوسط السعر عندكم كام؟",
            expected_keywords=["متوسط", "مليون"]
        )
    ],
    is_conversational=False
))
```

## Test Data

Tests run against actual data:
- **CSV**: `11-15_sample25.csv` (25 Hawabay units, 4M-37M EGP)
- **DOCX**: `bany_developer_profile.docx` (Developer information)

## Troubleshooting

### Connection Error
```
API Error: Connection refused
```
**Solution**: Check RAG API is running and URL is correct

### Empty Responses
```
❌ FAIL
Issues: Empty response
```
**Solution**: Check API health endpoint `/health`, verify GEMINI_API_KEY set

### Missing Keywords
```
⚠️  Missing keywords: sea view, beach view
```
**Solution**: Check generator prompt includes description extraction

### Slow Responses (>5s)
```
✅ PASS (6.73s)
```
**Solution**: Check RAG API resources (CPU/memory), index size

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Broker Behavior Tests
  run: |
    cd ai/rag
    python test_broker_behavior.py https://rag-api-dbgj63mjca-uc.a.run.app
```

### Exit Codes
- `0`: All tests passed
- `1`: One or more tests failed

## Performance Benchmarks

**Expected Response Times**:
- Simple queries (count, cheapest): < 1.5s
- Complex filters (multi-criteria): < 2.5s
- Conversational (context retrieval): < 2.0s

**Success Rate Targets**:
- Keyword validation: >90%
- Unit code accuracy: >95%
- Price range filtering: 100%

## Notes

1. **Session Management**: Conversational tests maintain session ID across queries; single-query tests create new sessions
2. **Rate Limiting**: Small 0.5s delay between conversational queries to avoid overwhelming API
3. **Stream Parsing**: Handles SSE (Server-Sent Events) format from `/query/stream` endpoint
4. **Arabic Support**: Full UTF-8 encoding for Arabic queries and responses

## Future Enhancements

- [ ] Add all 30 test cases (currently 10 implemented)
- [ ] Image URL validation (check generated_images paths)
- [ ] Pronunciation/ASR testing via orchestrator
- [ ] UI automation tests (Playwright/Selenium)
- [ ] Load testing (concurrent users)
- [ ] A/B testing (prompt variations)

---

**Last Updated**: November 29, 2025
