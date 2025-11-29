# Test Cases for Broker Behavior

**Project**: Real Estate Chatbot (AI-P)  
**Base Content**: Hawabay Compound (25 units) + Bany Developer Profile  
**Total Test Cases**: 30 (15 Conversational + 15 Single-Query)

---

## Part 1: Conversational Test Cases (15 cases, up to 7 queries each)

### Conversation 1: First-Time Buyer Journey
**Scenario**: New customer exploring options

1. "السلام عليكم، عايز أعرف عن الوحدات المتاحة"
2. "ايه أسعار الشقق عندكم؟"
3. "في حاجة أقل من 6 مليون؟"
4. "ورني أرخص 3 وحدات"
5. "الوحدة دي رقم 202 في مبنى 27/I كويسة؟"
6. "طب وأقساط المقدم كام؟"
7. "تمام، عايز أحجز معاد لمعاينة"

**Expected Behavior**: 
- Greet professionally
- Show units < 6M (codes: Hawabay/27/I/202, Hawabay/05/M/301, Hawabay/02/L/1)
- Extract details from description (floor, view, garden)
- Calculate 10% down payment
- Offer to connect with sales team

---

### Conversation 2: Sea View Preference
**Scenario**: Customer seeking sea-facing units

1. "عايز شقة مطلة على البحر"
2. "في كام وحدة؟"
3. "ايه أغلى واحدة فيهم؟"
4. "وأرخص واحدة؟"
5. "الفرق بينهم ايه؟"
6. "الأرخص دي كود كام؟"
7. "جميل، ممكن تبعتلي التفاصيل؟"

**Expected Behavior**:
- Filter by sea view/beach view
- Show most/least expensive
- Compare features (size, floor, amenities)
- Remember previous selection (pronoun resolution)
- Provide unit code and contact info

---

### Conversation 3: Villa with Garden
**Scenario**: Family looking for spacious villa

1. "محتاج فيلا كبيرة لعائلة"
2. "في فيلا بحديقة؟"
3. "مساحة الحديقة كام؟"
4. "والسعر كام؟"
5. "في أرخص منها؟"
6. "طب لو عايز أقسط على 4 سنين القسط هيبقى كام؟"
7. "ممكن معلومات عن المطور؟"

**Expected Behavior**:
- Filter villas with gardens
- Extract garden size from description
- Compare prices
- Calculate payment plan (4-year installment)
- Provide developer info from bany_developer_profile.docx

---

### Conversation 4: Budget-Constrained Search
**Scenario**: Customer with strict budget

1. "ميزانيتي 5 مليون بالظبط"
2. "في ايه في المبلغ ده؟"
3. "الوحدات دي مساحتها كام؟"
4. "أكبر مساحة فيهم؟"
5. "دي في أنهي دور؟"
6. "التشطيب ازاي؟"
7. "حلو، عايز أحجز"

**Expected Behavior**:
- Filter units ≤ 5M
- Show sizes
- Identify largest unit
- Extract floor info from description
- Extract finishing details
- Provide booking process

---

### Conversation 5: Amenities Focus
**Scenario**: Customer prioritizing facilities

1. "الكمباوند فيه ايه من خدمات؟"
2. "في حمام سباحة؟"
3. "وجيم؟"
4. "منطقة الأطفال كويسة؟"
5. "والأمن؟"
6. "في كلوب هاوس؟"
7. "تمام، دول متاحين في كل الوحدات؟"

**Expected Behavior**:
- Extract amenities from descriptions (clubhouse, gym, pool, kids area, security 24/7)
- Confirm all listed amenities
- Explain compound-wide availability
- Mention gated community benefits

---

### Conversation 6: Floor Preference
**Scenario**: Customer wants specific floor

1. "عايز شقة في الدور الأرضي"
2. "في كام وحدة؟"
3. "بيهم حديقة؟"
4. "أكبر حديقة كام متر؟"
5. "ودي سعرها كام؟"
6. "في أقل منها سعر؟"
7. "خلاص هاخد الأقل دي"

**Expected Behavior**:
- Filter ground floor (Gr) units
- Identify units with gardens
- Sort/compare garden sizes
- ProNoun resolution ("ودي" = that one)
- Confirm selection

---

### Conversation 7: Developer Information Deep Dive
**Scenario**: Customer researching developer credibility

1. "ايه معلومات عن شركة باني؟"
2. "عندهم مشاريع تانية؟"
3. "سمعتهم كويسة؟"
4. "بيشتغلوا في السوق من امتى؟"
5. "ضمانات الجودة عندهم؟"
6. "طب مشروع هاواي باي ايه مميزاته؟"
7. "تمام، مقتنع"

**Expected Behavior**:
- Retrieve Bany developer profile from RAG
- Mention portfolio/experience
- Highlight Hawabay project specifics
- Provide quality assurances
- Maintain professional credibility tone

---

### Conversation 8: Rooftop Sky Villa
**Scenario**: Luxury buyer wanting panoramic views

1. "عايز شقة بروف"
2. "في Sky Villa؟"
3. "مساحة الروف كام؟"
4. "الإطلالة ازاي؟"
5. "السعر كام؟"
6. "والتقسيط؟"
7. "ممكن أعرف الكود؟"

**Expected Behavior**:
- Filter Sky Villa units
- Extract roof size from description
- Mention panoramic view/sea view
- Provide price + installment options
- Give exact unit code

---

### Conversation 9: Comparison Shopping
**Scenario**: Customer comparing multiple units

1. "عايز أقارن بين وحدتين"
2. "ايه الفرق بين Hawabay/06/M/302 و Hawabay/05/M/303؟"
3. "أنهي واحدة فيهم أحسن إطلالة؟"
4. "والسعر؟"
5. "الفرق في السعر كام؟"
6. "طب أنهي واحدة تنصحني بيها؟"
7. "ليه؟"

**Expected Behavior**:
- Compare specified units
- Highlight view difference (sea view vs city view)
- Calculate price difference
- Provide professional recommendation based on value
- Justify with features

---

### Conversation 10: Payment Plan Exploration
**Scenario**: Customer exploring financing options

1. "نظام السداد عندكم ازاي؟"
2. "المقدم كام في المية؟"
3. "والباقي بيتقسم ازاي؟"
4. "في خيارات أقساط؟"
5. "لو دفعت على 5 سنين القسط هيبقى كام؟"
6. "طب لو 4 سنين؟"
7. "ايه الأفضل؟"

**Expected Behavior**:
- Explain 10% down payment
- Mention 4-year and 5-year plans
- Calculate from CSV columns (قسط 4 سنين, قسط 5 سنين)
- Compare monthly payments
- Suggest based on customer capability

---

###Conversation 11: Location & Proximity
**Scenario**: Customer asking about location benefits

1. "الكمباوند فين بالظبط؟"
2. "قريب من ايه؟"
3. "في مدارس قريبة؟"
4. "والخدمات اليومية؟"
5. "المواصلات سهلة؟"
6. "الموقع ده يعتبر prime location؟"
7. "تمام، الموقع ممتاز"

**Expected Behavior**:
- Extract location info from descriptions (prime location, قريب من الخدمات)
- Mention nearby facilities (schools, services)
- Confirm gated community benefits
- Highlight location as selling point

---

### Conversation 12: Master Bedroom Apartments
**Scenario**: Customer wants master bedroom

1. "عايز شقة فيها master bedroom"
2. "في كام وحدة متاحة؟"
3. "ايه أصغر مسا حة؟"
4. "دي سعرها كام؟"
5. "في وحدة تانية قريبة من السعر ده بس أكبر؟"
6. "الفرق في المساحة كام؟"
7. "يلا خد الأكبر"

**Expected Behavior**:
- Filter units with master bedroom mention
- Sort by size
- Find comparable prices with larger size
- Calculate size difference
- Confirm selection

---

### Conversation 13: Ready to Move
**Scenario**: Customer needs immediate occupancy

1. "محتاج شقة جاهزة دلوقتي"
2. "في وحدات ready to move؟"
3. "كلهم مفروشين؟"
4. "لا عايز بتشطيب بس"
5. "ايه أسعارهم؟"
6. "في حاجة 150 متر تقريباً؟"
7. "ممكن أشوفها امتى؟"

**Expected Behavior**:
- Filter ready to move units
- Clarify unfurnished (تشطيب كامل) vs furnished
- Show prices
- Filter by approximate size (150m²)
- Schedule viewing

---

### Conversation 14: Garden View Preference
**Scenario**: Customer avoiding sea/street views

1. "مش عايز مطل على الشارع"
2. "في بديل؟"
3. "garden view يعني ايه؟"
4. "في كام وحدة garden view؟"
5. "ايه أسعارهم؟"
6. "أيهم أحسن value for money؟"
7. "تمام، هاخد دي"

**Expected Behavior**:
- Understand negative preference (not city view)
- Suggest garden view alternatives
- Explain garden view benefits
- Filter and show count
- Analyze value proposition

---

### Conversation 15: Multi-Criteria Search
**Scenario**: Customer with multiple requirements

1. "عايز شقة 3 أدوار فما فوق، مساحة من 150-170 متر، بحديقة، سعر أقل من 7 مليون"
2. "في حاجة؟"
3. "كام وحدة لقيت؟"
4. "ورني أقلهم سعر"
5. "الوحدة دي مواصفاتها ايه بالظبط؟"
6. "كويسة، في تانية شبهها؟"
7. "خلاص قررت على الأولى"

**Expected Behavior**:
- Parse complex multi-filter query
- Filter by: floor ≥ 3, area 150-170m², has garden, price < 7M
- Count matches
- Sort by price
- Provide detailed specs
- Show similar alternatives
- Confirm final choice

---

## Part 2: Single-Query Test Cases (15 cases)

### Test 16: Cheapest Unit Query
**Query**: "ايه أرخص وحدة عندكم؟"

**Expected**:
- Return unit Hawabay/27/I/202 (4,070,000 EGP)
- Show code, price, size, floor
- Mention down payment option

---

### Test 17: Most Expensive Unit
**Query**: "أغلى وحدة بكام؟"

**Expected**:
- Return Villa Hawabay/07/B/7 or Hawabay/06/B/6 or Hawabay/05/B/5 (37,440,000 EGP)
- Highlight villa features (683m², garden 268m², roof 96m², sea view)

---

### Test 18: Total Units Available
**Query**: "عندكم كام وحدة متاحة؟"

**Expected**:
- Count: 25 units total
- Breakdown by type (X apartments, Y villas, Z garden villas)

---

### Test 19: Apartment vs Villa
**Query**: "ايه الفرق بين الشقق والفلل؟"

**Expected**:
- Explain apartments: smaller, elevator, compound living
- Explain villas: larger, private gardens, standalone feel, rooftop options
- Price range comparison

---

### Test 20: Specific Unit Code Query
**Query**: "عايز معلومات عن Hawabay/02/D/1"

**Expected**:
- Garden Villa, 375m², price 18,900,000 EGP
- Ground floor, garden 152m²
- Garden view, prime location
- Payment plan details

---

### Test 21: Average Price Query
**Query**: "متوسط السعر عندكم كام؟"

**Expected**:
- Calculate average from CSV (~11-12M EGP range)
- Mention price range (4M - 37M)
- Note: Most units 5-15M range

---

### Test 22: Largest Unit
**Query**: "أكبر وحدة مساحتها كام؟"

**Expected**:
- Villa 683m² (codes: Hawabay/07/B/7, Hawabay/06/B/6, Hawabay/05/B/5)
- Includes garden + roof
- Price and features

---

### Test 23: Smallest Unit
**Query**: "أصغر وحدة عندكم؟"

**Expected**:
- Apartment Hawabay/27/I/202 (110m²)
- Price 4,070,000 EGP
- 2nd floor, open view

---

### Test 24: Building Query
**Query**: "في حاجة في مبنى 05/M؟"

**Expected**:
- List all units in building 05/M (5 units)
- Range of floors, sizes, prices
- Mixed views (city view, garden view)

---

### Test 25: Third Floor Units
**Query**: "عايز شقة في الدور التالت"

**Expected**:
- Filter 3rd floor units
- Show 6-7 units
- Range of sizes and prices
- Views: sea view, city view, garden view

---

### Test 26: Developer Portfolio
**Query**: "باني شركة معروفة؟"

**Expected**:
- Retrieve info from bany_developer_profile.docx
- Mention company background
- Highlight credibility indicators
- List Hawabay as flagship project

---

### Test 27: Down Payment Calculation
**Query**: "لو الوحدة بـ10 مليون، المقدم هيبقى كام؟"

**Expected**:
- Calculate 10% = 1,000,000 EGP
- Mention remaining amount
- Suggest installment plans (4-year, 5-year)

---

### Test 28: Open Space Design
**Query**: "ايه يعني open space في الوحدات؟"

**Expected**:
- Explain open floor plan concept
- Mention living area + American kitchen integration
- Highlight modern design benefit
- Note: Common in apartments

---

### Test 29: Security Features
**Query**: "الأمن في الكمباوند ازاي؟"

**Expected**:
- Mention "security 24/7" from descriptions
- Explain gated community concept
- Highlight compound-wide surveillance
- Emphasize safety for families

---

### Test 30: Elevator Availability
**Query**: "كل المباني فيها أسانسير؟"

**Expected**:
- Confirm elevators in apartment buildings
- Note: Villas are standalone (ground floors with stairs to roof)
- Mention accessibility in compound design

---

## Success Criteria

### Generator Behavior:
- ✅ Professional Arabic tone throughout
- ✅ Extract features from descriptions (view, garden, roof, finishing)
- ✅ Calculate payment plans accurately
- ✅ Remember conversation context (pronoun resolution)
- ✅ Compare units logically
- ✅ Provide booking/next steps

### Selector Behavior:
- ✅ Accurately filter by price, size, floor, type
- ✅ Handle complex multi-criteria queries
- ✅ Sort by price/size when requested
- ✅ Return correct unit codes
- ✅ Handle pronoun references ("دي", "هاخد الأولى")
- ✅ Recognize location/amenity preferences

### RAG System:
- ✅ Retrieve Bany developer profile when asked
- ✅ Extract amenity lists from CSV descriptions
- ✅ Provide accurate image URLs
- ✅ Maintain conversation history
- ✅ Handle typos/variations in queries (e.g., "فيلا"/"villa")

---

## Test Execution Notes

1. Run tests in production environment (ai-p.run.app)
2. Test via voice (Arabic ASR) and text input
3. Verify image panel shows correct unit images
4. Check console for selector relevance scores
5. Validate payment calculations match CSV columns
6. Confirm developer info retrieval from docx RAG source

**Last Updated**: November 29, 2025
