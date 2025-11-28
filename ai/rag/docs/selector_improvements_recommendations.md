# Selector & Generator Improvements - Recommended Fixes

Based on the review of the last 4 cases, here are the recommended fixes:

## Issue 1: Conversation History Not Used for Follow-up Queries

### Problem:
- Case 4: Query "الوحده دي" (this unit) didn't trigger conversation history matching
- Payment/installment queries need unit context but selector returns 0 units

### Recommended Solutions:

#### Option A: Improve `_refers_to_history()` Detection (RECOMMENDED)
**Priority: HIGH**

Enhance the detection logic to catch more patterns:
- Add detection for payment/installment keywords combined with references
- Make detection more lenient for short queries
- Add detection for queries that mention payment/installment even without explicit pronouns

**Implementation:**
```python
def _refers_to_history(self, question: str) -> bool:
    """Enhanced heuristic to detect references to previous turns."""
    if not question:
        return False
    lowered = question.lower()
    
    # Existing pronoun patterns...
    reference_phrases = [
        "الشقة اللي قولتلك", "الوحدة اللي قولتلك", "اللي قولتلك عليها",
        "الكود بتاعها", "الكود بتاعه", "نفس الشقة", "نفس الوحدة",
        "دي اللي قولتلك عليها", "نفسها", "زي ما قلت", "دول", "دي",
        "اللي فاتوا", "اللي قولت", "اللي قلت", "منهم", "واحدة منهم",
        "شقة منهم", "الفيلا دي", "الفيلا ديت", "الشقة دي", "الشقة ديت",
        "الوحدة دي", "الوحدة ديت", "الهبله دي", "الهبله ديت",
        "الوحده دي", "الوحده ديت", "عن الوحده", "عن الشقة", "عن الفيلا"
    ]
    pronoun_hits = any(phrase in lowered for phrase in reference_phrases)
    
    # Payment/installment queries are likely follow-ups
    payment_keywords = ["سداد", "دفع", "قسط", "payment", "installment", 
                       "السداد", "الدفع", "القسط", "خريطة", "خريطه"]
    has_payment_keyword = any(keyword in lowered for keyword in payment_keywords)
    
    # If query has payment keywords, it's likely referring to a previous unit
    if has_payment_keyword:
        pronoun_hits = True
        logger.debug("Detected payment/installment query - likely refers to previous unit")
    
    # Very short queries (< 30 chars) with payment keywords are likely follow-ups
    if not pronoun_hits and len(question.strip()) < 30 and has_payment_keyword:
        pronoun_hits = True
    
    # Also treat very short questions with no numbers as likely references
    if not pronoun_hits and len(question.strip()) < 25 and not re.search(r"\d", question):
        pronoun_hits = True
    
    return pronoun_hits
```

#### Option B: Fallback to Last Units for Payment Queries
**Priority: MEDIUM**

If LLM_CODE returns 0 units but relevance is high and query mentions payment, use last_units:

```python
# After LLM_CODE execution
if len(rows) == 0 and relevance_score and relevance_score >= 0.7:
    payment_keywords = ["سداد", "دفع", "قسط", "payment", "installment"]
    if any(kw in clean_question.lower() for kw in payment_keywords) and last_units:
        logger.info("Payment query with high relevance but no units - using last_units as fallback")
        return UnitSelectorResult(
            code="# Fallback to last_units for payment query",
            rows=last_units[:effective_max_rows],
            raw_response="FALLBACK_LAST_UNITS",
            relevance_score=0.85,
            source="LAST_UNITS_MATCH",
            filters_applied=["Used last_units as fallback for payment query"]
        )
```

---

## Issue 2: Additional Message Matching Not Working

### Problem:
- Unit IDs from additional message (e.g., "203") not being matched
- Matching logic requires specific patterns

### Recommended Solutions:

#### Option A: Direct Unit ID Lookup (RECOMMENDED)
**Priority: HIGH**

Add direct lookup by Name column or Code ending:

```python
# In PRIORITY 0 section, after extracting additional_units
if additional_units:
    # Try direct lookup first
    matched_units = []
    for unit_id in additional_units:
        # Try matching by Name column (exact match)
        if 'Name' in self._df_cache.columns:
            name_matches = self._df_cache[self._df_cache['Name'].astype(str) == unit_id]
            if not name_matches.empty:
                matched_units.extend(name_matches.to_dict(orient='records'))
                continue
        
        # Try matching by Code ending (e.g., "/203")
        if 'Code' in self._df_cache.columns:
            code_matches = self._df_cache[
                self._df_cache['Code'].astype(str).str.endswith(f"/{unit_id}")
            ]
            if not code_matches.empty:
                matched_units.extend(code_matches.to_dict(orient='records'))
                continue
    
    if matched_units:
        # Remove duplicates
        seen = set()
        unique_units = []
        for unit in matched_units:
            unit_id = unit.get('Code') or unit.get('Name')
            if unit_id and unit_id not in seen:
                seen.add(unit_id)
                unique_units.append(unit)
        
        if unique_units:
            logger.info(f"Direct match found {len(unique_units)} units from additional message")
            return UnitSelectorResult(...)
    
    # Fallback to existing _match_explicit_units logic
    explicit_matches = self._match_explicit_units(...)
```

#### Option B: Improve `_match_explicit_units` for Standalone Numbers
**Priority: MEDIUM** (Already partially implemented)

Ensure standalone numbers are properly extracted and matched.

---

## Issue 3: Generator API Latency

### Problem:
- Case 3: 33.03s response time (too slow)
- Exceeds 15s threshold

### Recommended Solutions:

#### Option A: Add Retry Logic with Exponential Backoff
**Priority: MEDIUM**

```python
# In llm_generator.py
import time
from google.api_core import retry

def generate_stream(self, prompt: str, ...):
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # Existing generation code...
            response = self.client.generate_content(...)
            return response
        except (ServiceUnavailable, DeadlineExceeded) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API error (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
                time.sleep(delay)
                continue
            raise
```

#### Option B: Add Timeout Configuration
**Priority: LOW**

```python
# In llm_generator.py __init__
self.timeout = 30.0  # 30 second timeout

# In generate_stream
generation_config = {
    "temperature": temperature,
    "timeout": self.timeout,  # Add timeout
    **kwargs
}
```

#### Option C: Monitor and Alert on Slow Responses
**Priority: LOW** (Already implemented)

The logging already warns on responses > 15s. Consider adding metrics/alerts.

---

## Issue 4: Missing Relevance Scores

### Problem:
- Case 4: No relevance score logged
- Makes assessment difficult

### Recommended Solutions:

#### Option A: Ensure Relevance Score Extraction Always Works
**Priority: MEDIUM**

Improve the extraction logic to handle edge cases:

```python
def _extract_relevance_score(self, response: str) -> Optional[float]:
    """Extract relevance score from LLM response with better error handling."""
    if not response:
        return None
    
    # Try multiple patterns
    patterns = [
        r'RELEVANCE_SCORE:\s*([\d.]+)',
        r'relevance[_\s]*score[:\s]*([\d.]+)',
        r'Score:\s*([\d.]+)',
        r'([\d.]+)\s*\(relevance\)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                # Validate score is in range
                if 0.0 <= score <= 1.0:
                    return score
            except (ValueError, IndexError):
                continue
    
    # If no score found, return None (don't assume)
    logger.warning("Could not extract relevance score from LLM response")
    return None
```

#### Option B: Default Relevance Score Based on Results
**Priority: LOW**

If no relevance score but units found, assume moderate relevance:

```python
if relevance_score is None and len(rows) > 0:
    relevance_score = 0.7  # Assume moderate relevance
    logger.info("No relevance score extracted, assuming 0.7 based on units found")
```

---

## Issue 5: Payment Queries Need Unit Context

### Problem:
- Payment/installment queries return 0 units even when relevance is high
- These queries need specific unit context to answer

### Recommended Solutions:

#### Option A: Always Use Last Units for Payment Queries (RECOMMENDED)
**Priority: HIGH**

```python
# Add this check BEFORE LLM_CODE execution
payment_keywords = ["سداد", "دفع", "قسط", "payment", "installment", 
                   "السداد", "الدفع", "القسط", "خريطة", "خريطه"]
is_payment_query = any(kw in clean_question.lower() for kw in payment_keywords)

if is_payment_query and last_units:
    logger.info("Payment query detected - using last_units for context")
    return UnitSelectorResult(
        code="# Payment query - using last_units",
        rows=last_units[:effective_max_rows],
        raw_response="PAYMENT_QUERY_LAST_UNITS",
        relevance_score=0.9,
        source="LAST_UNITS_MATCH",
        filters_applied=["Payment query - using previously selected units"]
    )
```

#### Option B: Enhance LLM Prompt for Payment Queries
**Priority: MEDIUM**

Add specific instructions in the prompt for payment queries:

```python
# In _generate_code method
if any(kw in question.lower() for kw in ["سداد", "دفع", "قسط"]):
    instruction += """
    
    SPECIAL HANDLING FOR PAYMENT/INSTALLMENT QUERIES:
    If the query is about payment plans, installments, or payment methods:
    1. Check if conversation history mentions specific unit codes
    2. If history contains unit codes, filter by those codes
    3. Payment queries require specific unit context - don't return empty results
       if units were mentioned in the conversation
    """
```

---

## Implementation Priority

1. **HIGH Priority:**
   - Option 1A: Improve `_refers_to_history()` detection
   - Option 2A: Direct unit ID lookup for additional messages
   - Option 5A: Always use last_units for payment queries

2. **MEDIUM Priority:**
   - Option 1B: Fallback to last_units for payment queries
   - Option 4A: Ensure relevance score extraction always works
   - Option 5B: Enhance LLM prompt for payment queries

3. **LOW Priority:**
   - Option 3A: Add retry logic (if latency issues persist)
   - Option 3B: Add timeout configuration
   - Option 4B: Default relevance score

---

## Expected Impact

After implementing HIGH priority fixes:
- ✅ Payment queries will correctly use conversation history
- ✅ Additional message unit IDs will be matched reliably
- ✅ Follow-up queries with "الوحده دي" will work correctly
- ✅ Case 4 score should improve from 3.5/10 to 8+/10

