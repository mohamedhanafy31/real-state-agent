#!/usr/bin/env python3
"""
Test Script for Broker Behavior
Executes 30 test cases against the RAG system API
"""

import requests
import json
import time
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import sys


@dataclass
class TestQuery:
    """Single query in a test case"""
    query: str
    expected_keywords: List[str] = None
    expected_units: List[str] = None
    expected_price_range: tuple = None


@dataclass
class TestCase:
    """Complete test case with multiple queries"""
    id: int
    name: str
    scenario: str
    queries: List[TestQuery]
    is_conversational: bool = True


@dataclass
class TestResult:
    """Result of a test execution"""
    test_id: int
    test_name: str
    query: str
    passed: bool
    response: str
    units_returned: List[str]
    elapsed_time: float
    issues: List[str]


class BrokerTester:
    """Test executor for broker behavior"""
    
    def __init__(self, base_url: str = "https://rag-api-dbgj63mjca-uc.a.run.app"):
        self.base_url = base_url
        self.session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.results: List[TestResult] = []
    
    @staticmethod
    def _normalize_arabic_text(text: str) -> str:
        """Normalize Arabic text for comparison by mapping variations to standard forms."""
        variations = {
            'التالت': 'ثالث',
            'تاني': 'ثاني',
            'اول': 'أول',
            'ارخص': 'أرخص',
            'اغلى': 'أغلى',
            'اكبر': 'أكبر',
            'اصغر': 'أصغر',
            'تالت': 'ثالث',
            'تاني': 'ثاني',
            'تالتة': 'ثالثة',
            'تانية': 'ثانية',
        }
        normalized = text
        for variant, standard in variations.items():
            normalized = normalized.replace(variant, standard)
        return normalized
    
    @staticmethod
    def _extract_numbers(text: str) -> set:
        """Extract all numbers from text (with and without formatting)."""
        numbers = set()
        
        # Extract numbers with commas: "4,070,000"
        numbers_with_commas = re.findall(r'\d{1,3}(?:,\d{3})+', text)
        for num in numbers_with_commas:
            # Remove commas and add both formatted and unformatted versions
            unformatted = num.replace(',', '')
            numbers.add(unformatted)
            numbers.add(num)
        
        # Extract plain numbers (3+ digits): "4070000", "110", "683", "375"
        plain_numbers = re.findall(r'\b\d{3,}\b', text)
        numbers.update(plain_numbers)
        
        # Extract 2-digit numbers that might be important (like "25" for units count)
        two_digit_numbers = re.findall(r'\b\d{2}\b', text)
        numbers.update(two_digit_numbers)
        
        # Extract numbers with spaces: "4 070 000"
        numbers_with_spaces = re.findall(r'\d{1,3}(?:\s\d{3})+', text)
        for num in numbers_with_spaces:
            unformatted = num.replace(' ', '')
            numbers.add(unformatted)
            numbers.add(num)
        
        # Extract numbers in Arabic context (e.g., "110 متر", "683 متر مربع")
        # Look for numbers followed by Arabic measurement units
        arabic_measurements = re.findall(r'(\d+(?:,\d+)*(?:\s*\d+)*)\s*(?:متر|م²|م\s*مربع|m²|m\s*squared)', text, re.IGNORECASE)
        for num_str in arabic_measurements:
            # Clean and normalize
            cleaned = num_str.replace(',', '').replace(' ', '')
            if cleaned:
                numbers.add(cleaned)
                numbers.add(num_str.strip())
        
        return numbers
        
    def query_rag(self, question: str) -> Dict[str, Any]:
        """Send query to RAG API and return response"""
        url = f"{self.base_url}/query/stream"
        
        payload = {
            "question": question,
            "session_id": self.session_id,
            "retrieval_k": 5,
            "temperature": 0.7,
            "include_context": False
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            # Parse SSE stream
            full_text = ""
            metadata = {}
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        try:
                            data = json.loads(data_str)
                            if data.get('type') == 'metadata':
                                metadata = data
                            elif data.get('type') == 'chunk':
                                full_text += data.get('text', '')
                        except json.JSONDecodeError:
                            continue
            
            elapsed_time = time.time() - start_time
            
            return {
                "answer": full_text,
                "metadata": metadata,
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            return {
                "answer": "",
                "metadata": {},
                "elapsed_time": elapsed_time,
                "error": str(e)
            }
    
    def validate_response(
        self,
        response: str,
        metadata: Dict,
        expected_keywords: List[str] = None,
        expected_units: List[str] = None,
        expected_price_range: tuple = None
    ) -> tuple[bool, List[str]]:
        """Validate response against expectations"""
        issues = []
        
        if not response:
            issues.append("Empty response")
            return False, issues
        
        # Check for expected keywords (with normalization)
        if expected_keywords:
            missing_keywords = []
            response_normalized = self._normalize_arabic_text(response.lower())
            response_numbers = self._extract_numbers(response)
            
            for keyword in expected_keywords:
                keyword_normalized = self._normalize_arabic_text(keyword.lower())
                
                # Check if keyword is a number
                if keyword.isdigit() or (keyword.replace(',', '').isdigit()):
                    # Normalize the keyword number (remove commas/spaces)
                    keyword_num = keyword.replace(',', '').replace(' ', '')
                    if keyword_num not in response_numbers:
                        missing_keywords.append(keyword)
                # Check for Arabic/English variations
                elif keyword_normalized not in response_normalized:
                    # Also check if it's an English keyword that might have Arabic equivalent
                    # Common mappings
                    bilingual_map = {
                        'villa': ['فيلا', 'فيله'],
                        'apartment': ['شقة', 'شقه', 'شقق'],
                        'sea view': ['بحر', 'بحرية', 'بحرى', 'بحر مباشر', 'مطل على البحر', 'مطلة على البحر'],
                        'beach view': ['بحر', 'بحرية', 'بحرى', 'بحر مباشر', 'مطل على البحر', 'مطلة على البحر'],
                        'garden': ['جاردن', 'حديقة', 'حدائق'],
                        'security': ['أمن', 'حراسة', 'أمان'],
                        '24/7': ['24 ساعة', '24/7', 'على مدار الساعة', 'مدار الساعة'],
                        'gym': ['جيم', 'نادي رياضي'],
                        'pool': ['حمام سباحة', 'سباحة'],
                        'gated community': ['مجتمع مسور', 'كمبوند', 'مجتمع مغلق', 'مجتمع آمن'],
                        '3rd': ['ثالث', 'التالت', 'تالت', 'ثالثة', 'التالتة'],
                        'third': ['ثالث', 'التالت', 'تالت', 'ثالثة', 'التالتة'],
                        'million': ['مليون', 'م'],
                        'unit': ['وحدة', 'وحدات'],
                        'units': ['وحدة', 'وحدات'],
                        'تواصل': ['اتصال', 'تواصل', 'اتصل', 'تواصل معنا', 'اتصل بنا'],
                        'bany': ['باني', 'باني ديفيلوبر', 'bany developer'],
                    }
                    
                    # Check if keyword has Arabic equivalents
                    found = False
                    if keyword.lower() in bilingual_map:
                        for arabic_equiv in bilingual_map[keyword.lower()]:
                            if arabic_equiv in response_normalized:
                                found = True
                                break
                    
                    if not found:
                        missing_keywords.append(keyword)
            
            if missing_keywords:
                issues.append(f"Missing keywords: {', '.join(missing_keywords)}")
        
        # Check for expected unit codes
        units_returned = []
        if metadata.get('structured_units'):
            units_returned = [u.get('Code', '') for u in metadata['structured_units']]
        
        if expected_units:
            missing_units = []
            for unit in expected_units:
                if unit not in units_returned:
                    missing_units.append(unit)
            if missing_units:
                issues.append(f"Missing expected units: {', '.join(missing_units)}")
        
        # Check price range
        if expected_price_range and units_returned:
            min_price, max_price = expected_price_range
            for unit in metadata.get('structured_units', []):
                price = unit.get('Price', 0)
                if not (min_price <= price <= max_price):
                    issues.append(f"Unit {unit.get('Code')} price {price} outside range {min_price}-{max_price}")
        
        passed = len(issues) == 0
        return passed, issues
    
    def run_test_case(self, test_case: TestCase) -> List[TestResult]:
        """Execute a single test case"""
        print(f"\n{'='*80}")
        print(f"Test {test_case.id}: {test_case.name}")
        print(f"Scenario: {test_case.scenario}")
        print(f"{'='*80}")
        
        results = []
        
        # Reset session for non-conversational tests
        if not test_case.is_conversational:
            self.session_id = f"test_{test_case.id}_{datetime.now().strftime('%H%M%S')}"
        
        for idx, query in enumerate(test_case.queries, 1):
            print(f"\nQuery {idx}/{len(test_case.queries)}: {query.query}")
            
            # Execute query
            response_data = self.query_rag(query.query)
            
            if 'error' in response_data:
                print(f"  ❌ ERROR: {response_data['error']}")
                result = TestResult(
                    test_id=test_case.id,
                    test_name=test_case.name,
                    query=query.query,
                    passed=False,
                    response="",
                    units_returned=[],
                    elapsed_time=response_data['elapsed_time'],
                    issues=[f"API Error: {response_data['error']}"]
                )
                results.append(result)
                continue
            
            # Validate response
            passed, issues = self.validate_response(
                response_data['answer'],
                response_data['metadata'],
                query.expected_keywords,
                query.expected_units,
                query.expected_price_range
            )
            
            # Extract units
            units_returned = []
            if response_data['metadata'].get('structured_units'):
                units_returned = [u.get('Code', '') for u in response_data['metadata']['structured_units']]
            
            # Print results
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} ({response_data['elapsed_time']:.2f}s)")
            if units_returned:
                print(f"  Units: {', '.join(units_returned)}")
            if issues:
                for issue in issues:
                    print(f"  ⚠️  {issue}")
            
            # Truncate long responses for display
            response_preview = response_data['answer'][:200] + "..." if len(response_data['answer']) > 200 else response_data['answer']
            print(f"  Response: {response_preview}")
            
            result = TestResult(
                test_id=test_case.id,
                test_name=test_case.name,
                query=query.query,
                passed=passed,
                response=response_data['answer'],
                units_returned=units_returned,
                elapsed_time=response_data['elapsed_time'],
                issues=issues
            )
            results.append(result)
            
            # Small delay between queries in conversation
            if test_case.is_conversational and idx < len(test_case.queries):
                time.sleep(0.5)
        
        return results
    
    def generate_report(self):
        """Generate test report"""
        print(f"\n{'='*80}")
        print("TEST REPORT")
        print(f"{'='*80}")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print(f"\nTotal Queries: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        
        avg_time = sum(r.elapsed_time for r in self.results) / total if total > 0 else 0
        print(f"Average Response Time: {avg_time:.2f}s")
        
        # Group by test
        test_summary = {}
        for result in self.results:
            if result.test_name not in test_summary:
                test_summary[result.test_name] = {"passed": 0, "failed": 0}
            if result.passed:
                test_summary[result.test_name]["passed"] += 1
            else:
                test_summary[result.test_name]["failed"] += 1
        
        print(f"\n{'Test Name':<50} {'Pass':<6} {'Fail':<6}")
        print("-" * 65)
        for name, stats in test_summary.items():
            print(f"{name:<50} {stats['passed']:<6} {stats['failed']:<6}")
        
        # Failed queries
        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            print(f"\n{'='*80}")
            print("FAILED QUERIES")
            print(f"{'='*80}")
            for result in failed_results:
                print(f"\nTest: {result.test_name}")
                print(f"Query: {result.query}")
                print(f"Issues:")
                for issue in result.issues:
                    print(f"  - {issue}")
        
        # Save to file
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump([{
                "test_id": r.test_id,
                "test_name": r.test_name,
                "query": r.query,
                "passed": r.passed,
                "response": r.response,
                "units_returned": r.units_returned,
                "elapsed_time": r.elapsed_time,
                "issues": r.issues
            } for r in self.results], f, ensure_ascii=False, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")


def get_test_cases() -> List[TestCase]:
    """Define all 30 test cases"""
    
    test_cases = []
    
    # Conversation 1: First-Time Buyer Journey
    test_cases.append(TestCase(
        id=1,
        name="First-Time Buyer Journey",
        scenario="New customer exploring options",
        queries=[
            TestQuery("السلام عليكم، عايز أعرف عن الوحدات المتاحة", expected_keywords=["وحدة", "متاح"]),
            TestQuery("ايه أسعار الشقق عندكم؟", expected_keywords=["سعر", "مليون"]),
            TestQuery("في حاجة أقل من 6 مليون؟", expected_price_range=(0, 6000000)),
            TestQuery("ورني أرخص 3 وحدات", expected_keywords=["أرخص"]),
            TestQuery("الوحدة دي رقم 202 في مبنى 27/I كويسة؟", expected_units=["Hawabay/27/I/202"]),
            TestQuery("طب وأقساط المقدم كام؟", expected_keywords=["مقدم", "10%"]),
            TestQuery("تمام، عايز أحجز معاد لمعاينة", expected_keywords=["معاينة", "تواصل"])
        ]
    ))
    
    # Conversation 2: Sea View Preference
    test_cases.append(TestCase(
        id=2,
        name="Sea View Preference",
        scenario="Customer seeking sea-facing units",
        queries=[
            TestQuery("عايز شقة مطلة على البحر", expected_keywords=["sea view", "beach view", "بحر"]),
            TestQuery("في كام وحدة؟"),
            TestQuery("ايه أغلى واحدة فيهم؟"),
            TestQuery("وأرخص واحدة؟"),
            TestQuery("الفرق بينهم ايه؟"),
            TestQuery("الأرخص دي كود كام؟"),
            TestQuery("جميل، ممكن تبعتلي التفاصيل؟")
        ]
    ))
    
    # Conversation 3: Villa with Garden
    test_cases.append(TestCase(
        id=3,
        name="Villa with Garden",
        scenario="Family looking for spacious villa",
        queries=[
            TestQuery("محتاج فيلا كبيرة لعائلة", expected_keywords=["villa", "فيلا"]),
            TestQuery("في فيلا بحديقة؟", expected_keywords=["garden", "حديقة"]),
            TestQuery("مساحة الحديقة كام؟"),
            TestQuery("والسعر كام؟"),
            TestQuery("في أرخص منها؟"),
            TestQuery("طب لو عايز أقسط على 4 سنين القسط هيبقى كام؟", expected_keywords=["قسط", "4 سنين"]),
            TestQuery("ممكن معلومات عن المطور؟", expected_keywords=["باني", "bany", "مطور"])
        ]
    ))
    
    # Single-Query Test 16: Cheapest Unit
    test_cases.append(TestCase(
        id=16,
        name="Cheapest Unit Query",
        scenario="Query for cheapest unit",
        queries=[
            TestQuery(
                "ايه أرخص وحدة عندكم؟",
                expected_units=["Hawabay/27/I/202"],
                expected_keywords=["4070000", "110"]
            )
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 17: Most Expensive
    test_cases.append(TestCase(
        id=17,
        name="Most Expensive Unit",
        scenario="Query for most expensive unit",
        queries=[
            TestQuery(
                "أغلى وحدة بكام؟",
                expected_keywords=["37440000", "villa", "683"],
                expected_price_range=(37000000, 38000000)
            )
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 18: Total Units
    test_cases.append(TestCase(
        id=18,
        name="Total Units Available",
        scenario="Count total available units",
        queries=[
            TestQuery("عندكم كام وحدة متاحة؟", expected_keywords=["25", "وحدة"])
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 20: Specific Unit Code
    test_cases.append(TestCase(
        id=20,
        name="Specific Unit Code Query",
        scenario="Query specific unit by code",
        queries=[
            TestQuery(
                "عايز معلومات عن Hawabay/02/D/1",
                expected_units=["Hawabay/02/D/1"],
                expected_keywords=["Garden Villa", "375", "18900000"]
            )
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 24: Building Query
    test_cases.append(TestCase(
        id=24,
        name="Building Query",
        scenario="Query units in specific building",
        queries=[
            TestQuery(
                "في حاجة في مبنى 05/M؟",
                expected_keywords=["05/M"]
            )
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 25: Third Floor
    test_cases.append(TestCase(
        id=25,
        name="Third Floor Units",
        scenario="Query 3rd floor units",
        queries=[
            TestQuery(
                "عايز شقة في الدور التالت",
                expected_keywords=["3rd", "تالت", "ثالث"]
            )
        ],
        is_conversational=False
    ))
    
    # Single-Query Test 29: Security
    test_cases.append(TestCase(
        id=29,
        name="Security Features",
        scenario="Query about security",
        queries=[
            TestQuery(
                "الأمن في الكمباوند ازاي؟",
                expected_keywords=["security", "24/7", "gated community", "أمن"]
            )
        ],
        is_conversational=False
    ))
    
    return test_cases


def main():
    """Main test execution"""
    print("="*80)
    print("BROKER BEHAVIOR TEST SUITE")
    print("="*80)
    
    # Check if custom URL provided
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://rag-api-dbgj63mjca-uc.a.run.app"
    print(f"\nRAG API URL: {base_url}")
    
    # Initialize tester
    tester = BrokerTester(base_url)
    
    # Get test cases (subset for demo - add all 30 if needed)
    test_cases = get_test_cases()
    
    print(f"\nTotal Test Cases: {len(test_cases)}")
    print(f"Starting tests at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    for test_case in test_cases:
        results = tester.run_test_case(test_case)
        tester.results.extend(results)
    
    # Generate report
    tester.generate_report()
    
    # Return exit code
    failed_count = sum(1 for r in tester.results if not r.passed)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
