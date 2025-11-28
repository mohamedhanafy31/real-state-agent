"""
LLM-powered unit selector that generates pandas filtering code and executes it safely.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class UnitSelectorResult:
    """Container for the selector output."""

    code: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[str] = None
    relevance_score: Optional[float] = None  # Score 0.0-1.0 indicating how well query matches CSV data
    # New metadata fields to help downstream components (generator, logging, evaluation)
    source: Optional[str] = None  # e.g. "EXPLICIT_MATCH", "HISTORY_MATCH", "LLM_CODE"
    filters_applied: Optional[List[str]] = None  # Human-readable filters description
    sort_applied: Optional[Dict[str, Any]] = None  # e.g. {"by": "Price", "direction": "asc", "limit": 3}

    @property
    def success(self) -> bool:
        return not self.error


class UnitSelector:
    """
    Generates pandas code via Gemini and executes it in a constrained environment
    to filter units from the CSV dataset.
    """

    _CODE_MARKER = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    _BLOCKED_PATTERNS = (
        "__",
        "import os",
        "import sys",
        "os.",
        "sys.",
        "subprocess",
        "eval(",
        "exec(",
        "open(",
        "shutil",
        "socket",
        "requests",
        "http.",
        "Path(",
        "pickle",
        "print(",
        "print ",
        # Block common hardcoded CSV path patterns (but allow CSV_PATH variable)
        '".csv"',
        "'.csv'",
    )
    _RESULT_CANDIDATES = (
        "selected_units",
        "result_df",
        "result",
        "filtered",
        "affordable",
        "matches",
    )

    def __init__(
        self,
        csv_path: str | Path,
        api_key: Optional[str],
        model_name: str = "gemini-2.0-flash",
        max_rows: int = 10,
    ):
        if not api_key:
            raise ValueError("Gemini API key is required for UnitSelector.")

        self.csv_path = Path(csv_path).resolve()
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        self.max_rows = max_rows
        self.model_name = model_name
        # Load dataset once for rule-based shortcuts
        try:
            self._df_cache = pd.read_csv(self.csv_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to read CSV at {self.csv_path}: {exc}") from exc
        if "Code" in self._df_cache.columns:
            self._normalized_codes = (
                self._df_cache["Code"]
                .astype(str)
                .str.replace(r"\s+", "", regex=True)
                .str.lower()
            )
        else:
            self._normalized_codes = pd.Series(index=self._df_cache.index, dtype=str)
        if "Name" in self._df_cache.columns:
            self._name_strings = self._df_cache["Name"].astype(str).str.strip()
        else:
            self._name_strings = pd.Series(index=self._df_cache.index, dtype=str)

        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - import error surfaced at runtime
            raise ImportError(
                "google-generativeai is required for UnitSelector. "
                "Install it with: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def select_units(
        self,
        question: str,
        conversation_history: Optional[str] = None,
        last_units: Optional[List[Dict[str, Any]]] = None
    ) -> UnitSelectorResult:
        """
        Generate pandas filtering code for the user question and execute it.
        """
        raw_response = ""
        cleaned_code = ""

        try:
            # Parse additional message if present (format: "مهتم بالوحدات :\n<unit_list>")
            additional_units = None
            clean_question = question
            if "مهتم بالوحدات" in question or "interested in units" in question.lower():
                parts = question.split("مهتم بالوحدات")
                if len(parts) > 1:
                    clean_question = parts[0].strip()
                    unit_list_part = parts[1].split(":", 1)
                    if len(unit_list_part) > 1:
                        unit_list_str = unit_list_part[1].strip()
                        # Extract unit IDs/titles (comma-separated or newline-separated)
                        additional_units = [u.strip() for u in unit_list_str.replace("\n", ",").split(",") if u.strip()]
                        logger.info(
                            "Unit selector - Extracted %d units from additional message: %s",
                            len(additional_units),
                            additional_units[:3]  # Log first 3
                        )
            
            # Extract requested number from question (e.g., "top 3", "first 5", "أول 3")
            requested_count = self._extract_requested_count(clean_question)
            # Use the smaller of requested count or max_rows
            effective_max_rows = min(requested_count, self.max_rows) if requested_count else self.max_rows

            search_text = f"{conversation_history}\n{clean_question}" if conversation_history else clean_question
            
            # PRIORITY 0: If additional_units are provided, try to match them explicitly
            if additional_units:
                # Format additional units for matching (add "كود" prefix if it's just a number)
                formatted_units = []
                for unit in additional_units:
                    # If it's just a number, format it as "كود 203" to match the pattern
                    if unit.isdigit():
                        formatted_units.append(f"كود {unit}")
                    else:
                        formatted_units.append(unit)
                
                explicit_matches = self._match_explicit_units("\n".join(formatted_units), effective_max_rows)
                if explicit_matches:
                    logger.info(
                        "Unit selector EXPLICIT_MATCH - Matched %d units from additional message (relevance: 1.00)",
                        len(explicit_matches)
                    )
                    return UnitSelectorResult(
                        code="# Explicit match from additional message",
                        rows=explicit_matches,
                        raw_response="EXPLICIT_MATCH_FROM_ADDITIONAL",
                        relevance_score=1.0,
                        source="EXPLICIT_MATCH",
                        filters_applied=[
                            f"Matched units from additional message: {', '.join(additional_units[:3])}"
                        ],
                    )
                else:
                    logger.warning(
                        "Unit selector - Could not match units from additional message: %s",
                        additional_units
                    )

            # PRIORITY 1: If question refers to previous units and we have last_units, use them first
            if last_units and self._refers_to_history(clean_question):
                # Try to filter within last_units based on the question
                filtered_from_last = self._filter_within_last_units(
                    clean_question, last_units, effective_max_rows
                )
                if filtered_from_last:
                    logger.info(
                        "Unit selector LAST_UNITS_MATCH - Resolved pronoun reference using last_units (%d rows from %d, relevance: 0.95)",
                        len(filtered_from_last),
                        len(last_units),
                    )
                    return UnitSelectorResult(
                        code="# Last units pronoun match",
                        rows=filtered_from_last,
                        raw_response="LAST_UNITS_MATCH",
                        relevance_score=0.95,
                        source="LAST_UNITS_MATCH",
                        filters_applied=[
                            f"Filtered within {len(last_units)} previously selected units based on pronoun/reference"
                        ],
                    )
                # If no filter applied but we have last_units and query is referential, return all last_units
                if len(last_units) <= effective_max_rows:
                    logger.info(
                        "Unit selector LAST_UNITS_MATCH - Returning all last_units for pronoun reference (%d rows, relevance: 0.95)",
                        len(last_units),
                    )
                    return UnitSelectorResult(
                        code="# Last units pronoun match (all)",
                        rows=last_units[:effective_max_rows],
                        raw_response="LAST_UNITS_MATCH_ALL",
                        relevance_score=0.95,
                        source="LAST_UNITS_MATCH",
                        filters_applied=[
                            f"Returned all {len(last_units)} previously selected units (pronoun reference)"
                        ],
                    )

            # PRIORITY 2: If question refers back to previous turns, try to resolve using history only.
            if conversation_history and self._refers_to_history(clean_question):
                history_rows = self._match_explicit_units(conversation_history, effective_max_rows)
                if history_rows:
                    logger.info(
                        "Unit selector HISTORY_MATCH - Resolved reference to previous turn (%d rows, relevance: 0.95)",
                        len(history_rows),
                    )
                    return UnitSelectorResult(
                        code="# History reference match",
                        rows=history_rows,
                        raw_response="HISTORY_MATCH",
                        relevance_score=0.95,
                        source="HISTORY_MATCH",
                        filters_applied=[
                            "Reused explicit unit codes/numbers from conversation history"
                        ],
                    )

            explicit_rows = self._match_explicit_units(search_text, effective_max_rows)
            if explicit_rows is not None:
                logger.info(
                    "Unit selector EXPLICIT_MATCH - Returning %d explicit matches (bypassing LLM, relevance: 1.00)",
                    len(explicit_rows),
                )
                return UnitSelectorResult(
                    code="# Explicit selector match",
                    rows=explicit_rows,
                    raw_response="EXPLICIT_MATCH",
                    relevance_score=1.0,
                    source="EXPLICIT_MATCH",
                    filters_applied=[
                        "Matched explicit unit codes/IDs and/or numeric codes in question/history"
                    ],
                )
            
            raw_response = self._generate_code(clean_question, conversation_history=conversation_history)
            cleaned_code = self._extract_code(raw_response)
            if not cleaned_code:
                raise ValueError("LLM response did not contain executable code block.")

            # Extract relevance score from response
            relevance_score = self._extract_relevance_score(raw_response)
            
            # Log relevance score for assessment
            if relevance_score is not None:
                logger.info(
                    "Unit selector LLM_CODE - Relevance score: %.2f (query: %s)",
                    relevance_score,
                    clean_question[:50] + "..." if len(clean_question) > 50 else clean_question
                )
            else:
                logger.warning("Unit selector LLM_CODE - No relevance score extracted from LLM response")

            rows = self._execute_code(cleaned_code, effective_max_rows)
            
            # If relevance score is very low (< 0.3), force empty results
            # This indicates the query is not about CSV units (e.g., company info, developer profile)
            if relevance_score is not None and relevance_score < 0.3:
                logger.info(f"Low relevance score ({relevance_score:.2f}) detected. Forcing empty results.")
                rows = []
            
            # Log selector result summary
            logger.info(
                "Unit selector LLM_CODE - Selected %d units (relevance: %s, source: LLM_CODE)",
                len(rows),
                f"{relevance_score:.2f}" if relevance_score is not None else "N/A"
            )
            
            return UnitSelectorResult(
                code=cleaned_code,
                rows=rows,
                raw_response=raw_response,
                relevance_score=relevance_score,
                source="LLM_CODE",
            )
        except Exception as exc:  # pragma: no cover - defensive, runtime logging
            logger.warning("Unit selection failed: %s", exc)
            # Try to extract relevance score even on error
            relevance_score = None
            if raw_response:
                relevance_score = self._extract_relevance_score(raw_response)
            
            # If relevance score is very low, the error might be expected (non-CSV query)
            if relevance_score is not None and relevance_score < 0.3:
                logger.info(f"Low relevance score ({relevance_score:.2f}) with error. Likely non-CSV query.")
            
            return UnitSelectorResult(
                code=cleaned_code,
                rows=[],
                error=str(exc),
                raw_response=raw_response or cleaned_code,
                relevance_score=relevance_score,
            )

    def _generate_code(self, question: str, conversation_history: Optional[str] = None) -> str:
        """Ask Gemini to produce pandas code for the given question."""
        # Read CSV to get column names and sample data
        try:
            df_sample = pd.read_csv(self.csv_path, nrows=1)
            column_names = list(df_sample.columns)
            
            # Get sample values for key columns
            sample_values = {}
            key_columns = ['Usage', 'Floor', 'Building']
            for col in key_columns:
                if col in df_sample.columns:
                    # Get unique values from full CSV for these columns
                    try:
                        unique_vals = pd.read_csv(self.csv_path, usecols=[col])[col].unique()[:5]
                        sample_values[col] = [str(v) for v in unique_vals]
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Could not read CSV for schema info: {e}")
            column_names = []
            sample_values = {}
        
        # Build column info string
        column_info = ""
        if column_names:
            column_info = f"Available columns: {', '.join(column_names)}\n"
            if sample_values:
                column_info += "\nSample values for key columns:\n"
                for col, vals in sample_values.items():
                    column_info += f"  - {col}: {vals}\n"
        
        history_block = ""
        if conversation_history:
            history_block = (
                "Conversation history (latest first):\n"
                f"{conversation_history.strip()}\n\n"
                "Use this history to resolve pronouns or references such as "
                "\"الوحدة اللي كنا بنتكلم عنها\".\n\n"
            )

        instruction = (
            "You are an assistant that writes secure pandas code to filter real-estate units.\n\n"
            "QUERY AUTOCORRECT - IMPORTANT:\n"
            "Before processing the query, automatically correct common spelling mistakes and typos:\n"
            "- Arabic common mistakes: 'شهور' → 'شقق' (months → apartments), 'عجلات' → 'شقق' (wheels → apartments), 'موديلات' → 'شقق' (models → apartments), 'موبايلات' → 'شقق' (phones → apartments)\n"
            "- Fix incomplete words: 'ثلاثه' → 'ثلاثة', 'ثلاث' → 'ثلاثة', 'ارخص' → 'أرخص'\n"
            "- Normalize variations: 'فيلا' = 'فيله' = 'فيله', 'شقة' = 'شقه' = 'شقق'\n"
            "- Fix common typos: 'السادات' → 'السداد' (payment plan), 'الهبله' → 'الفيلا' (villa)\n"
            "- Remove extra spaces and normalize punctuation\n"
            "Apply these corrections automatically when interpreting the query.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. The CSV file is ALREADY LOADED in variable 'df'. DO NOT call pd.read_csv() again.\n"
            "2. The CSV_PATH variable is available but you should use 'df' directly (it's already loaded).\n"
            "3. DO NOT hardcode any file paths. The data is already in the 'df' variable.\n"
            "4. DO NOT define functions. Write direct code execution only.\n"
            "5. DO NOT use try/except blocks. The data is guaranteed to be available.\n"
            "6. DO NOT use print() or any print statements. Just assign to 'selected_units'.\n"
            "7. Store the final filtered dataframe in a variable named `selected_units` (exactly this name).\n"
            "8. Use vectorized pandas operations with pandas (pd). Avoid loops. Use pandas for speed and efficiency.\n"
            "9. Limit results to top 50 rows using .head(50).\n\n"
            "IMPORTANT: If the query is about company information, developer profile, company history, "
            "company values, partnerships, awards, team information, or any non-unit-related information, "
            "return an EMPTY DataFrame: selected_units = pd.DataFrame()\n\n"
            "TEXT MATCHING - CRITICAL FOR ARABIC QUERIES:\n"
            "When searching text in Description or other text columns, use FLEXIBLE patterns with regex OR conditions.\n"
            "DO NOT search for exact query phrases. Instead, search for semantic equivalents and variations.\n\n"
            "Examples of flexible text matching:\n"
            "- For 'sea view' or 'overlooking sea' queries, use: df['Description'].str.contains('بحر|sea view|beach view|مطل على البحر', case=False, na=False)\n"
            "- For 'apartment' queries, use: df['Usage'] == 'Apartment' OR df['Description'].str.contains('شقة|apartment', case=False, na=False)\n"
            "- For 'garden' queries, use: df['Description'].str.contains('حديقة|garden|جاردن', case=False, na=False)\n"
            "- For 'villa' queries, use: df['Usage'].str.contains('Villa|villa|فيلا', case=False, na=False)\n\n"
            "Arabic Text Variations - Common Patterns:\n"
            "- Sea/Beach: 'بحر', 'sea view', 'beach view', 'مطل على البحر', 'مطلة على البحر', 'تطل على البحر', 'بتطل علي البحر'\n"
            "- Apartment: 'شقة', 'شقق', 'apartment', 'Apartment'\n"
            "- Villa: 'فيلا', 'villa', 'Villa'\n"
            "- Garden: 'حديقة', 'جاردن', 'garden', 'Garden'\n"
            "- City view: 'city view', 'مطل على الشارع', 'open view'\n"
            "- Cheap/Expensive: 'أرخص', 'أغلى', 'cheapest', 'expensive', 'lowest', 'highest'\n\n"
            "ALWAYS use regex patterns with pipe (|) for OR conditions when matching text:\n"
            "  GOOD: df['Description'].str.contains('بحر|sea view|beach view', case=False, na=False)\n"
            "  BAD:  df['Description'].str.contains('بتطل علي البحر', case=False, na=False)  # Too specific!\n\n"
            f"{column_info}\n"
            "Return your response in the following format:\n"
            "```python\n"
            "# Your pandas code here\n"
            "```\n\n"
            "RELEVANCE_SCORE: <score>\n"
            "Where <score> is a float between 0.0 and 1.0 indicating how well the query relates to the CSV data:\n"
            "- 1.0: Perfect match, query directly maps to CSV columns/values\n"
            "- 0.8-0.9: Very good match, query can be answered using CSV data\n"
            "- 0.6-0.7: Good match, query partially matches CSV structure\n"
            "- 0.4-0.5: Moderate match, query has some relation to CSV data\n"
            "- 0.2-0.3: Weak match, query barely relates to CSV data\n"
            "- 0.0-0.1: No match, query cannot be answered from CSV data (e.g., company info, developer profile)\n\n"
            "Code requirements:\n"
            "1. If query is about units (price, area, type, features, etc.), filter the dataframe 'df'.\n"
            "2. If query is NOT about units (company info, developer, etc.), return: selected_units = pd.DataFrame()\n"
            "3. Clean numeric fields if needed (Price, Area, Garden, Roof).\n"
            "4. Store result in 'selected_units' variable.\n"
            "5. Use .head(50) to limit results (if not empty).\n"
            "6. For text searches, ALWAYS use flexible regex patterns with multiple alternatives (use | for OR).\n"
            "7. When filtering by Usage type, prefer exact column match: df['Usage'] == 'Apartment'\n"
            "8. When filtering by Description text, use flexible patterns: df['Description'].str.contains('pattern1|pattern2|pattern3', case=False, na=False)\n"
        )

        question_block = question
        if conversation_history:
            question_block = f"{history_block}Current user question:\n{question}"

        prompt = f"{instruction}\n\nUser question:\n{question_block}"
        response = self.model.generate_content(prompt)
        return response.text or ""

    def _extract_code(self, text: str) -> str:
        """Extract python code from markdown fences if present."""
        if not text:
            return ""

        match = self._CODE_MARKER.search(text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_relevance_score(self, text: str) -> Optional[float]:
        """Extract relevance score from LLM response."""
        if not text:
            return None
        
        import re
        
        # Look for RELEVANCE_SCORE: <number> pattern
        # Case insensitive, allows for various formats
        patterns = [
            r'RELEVANCE_SCORE:\s*([0-9.]+)',
            r'relevance[_\s]score[:\s]+([0-9.]+)',
            r'score[:\s]+([0-9.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    # Clamp to 0.0-1.0 range
                    score = max(0.0, min(1.0, score))
                    return score
                except (ValueError, IndexError):
                    continue
        
        return None

    def _extract_requested_count(self, question: str) -> Optional[int]:
        """Extract the number of units requested from the question."""
        import re
        
        question_lower = question.lower()
        
        # FIRST: Check for explicit numbers (priority - if user says "5", respect it)
        # Patterns to match numbers in Arabic and English
        # Arabic: "أول 3", "أول ثلاثة", "3 وحدات", "ثلاث وحدات"
        # English: "top 3", "first 5", "3 units", "cheapest 3"
        patterns = [
            r'(?:top|first|cheapest|lowest|أول|أرخص|أقل)\s*(\d+)',  # "top 3", "أول 3"
            r'(\d+)\s*(?:units?|وحدات?|شقق?|فلل?)',  # "3 units", "3 وحدات"
            r'(\d+)\s*(?:cheapest|lowest|أرخص|أقل)',  # "3 cheapest", "3 أرخص"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question_lower, re.IGNORECASE)
            if match:
                try:
                    count = int(match.group(1))
                    if 1 <= count <= 100:  # Reasonable range
                        return count
                except ValueError:
                    continue
        
        # Check for Arabic written numbers (basic)
        arabic_numbers = {
            'واحد': 1, 'واحدة': 1, 'اثنين': 2, 'اثنتين': 2,
            'ثلاثة': 3, 'ثلاث': 3, 'أربعة': 4, 'أربع': 4,
            'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6,
            'سبعة': 7, 'سبع': 7, 'ثمانية': 8, 'ثمان': 8,
            'تسعة': 9, 'تسع': 9, 'عشرة': 10, 'عشر': 10
        }
        
        for arabic_word, num in arabic_numbers.items():
            if arabic_word in question_lower:
                return num
        
        # SECOND: Check for singular superlatives (the most/least expensive, cheapest, etc.)
        # These should return 1 unit when asking for "the" or "أي" (which/what)
        # Patterns that indicate asking for a single item
        singular_keywords = [
            r'أي\s*(?:هي|هو)\s*(?:أغلى|أرخص|أكبر|أصغر|أعلى|أقل|اغلي|اغلى)',  # "أي هي أغلى"
            r'(?:أي|ايه|إيه)\s*(?:هي|هو)\s*(?:أغلى|أرخص|أكبر|أصغر|أعلى|أقل|اغلي|اغلى)',  # "أي هي أغلى"
            r'(?:the|أي|ايه|إيه)\s+(?:most|أغلى|أرخص|أكبر|أصغر|أعلى|أقل|اغلي|اغلى|cheapest|expensive|largest|smallest|highest|lowest)',
            r'(?:most|أغلى|أرخص|أكبر|أصغر|أعلى|أقل|اغلي|اغلى|cheapest|expensive|largest|smallest|highest|lowest)\s+(?:one|وحدة|شقة|فيلا|unit|apartment|villa)',
            r'(?:أغلى|اغلي|اغلى)\s+(?:شقة|وحدة|فيلا|apartment|unit|villa)',  # "أغلى شقة"
            r'(?:أرخص)\s+(?:شقة|وحدة|فيلا|apartment|unit|villa)',  # "أرخص شقة"
            r'(?:the|أي|ايه|إيه)\s+(?:best|worst|أفضل|أسوأ)',
        ]
        
        for pattern in singular_keywords:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return 1
        
        return None

    def _execute_code(self, code: str, max_rows: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute generated pandas code with safety checks."""
        lowered = code.lower()
        for pattern in self._BLOCKED_PATTERNS:
            # Special handling for CSV path patterns
            if pattern in ('".csv"', "'.csv'"):
                # Block if it's a hardcoded path (contains quotes), but allow CSV_PATH
                if pattern in lowered and 'csv_path' not in lowered:
                    raise ValueError(
                        "Disallowed pattern detected: hardcoded CSV path. "
                        "Use the pre-loaded 'df' variable instead of pd.read_csv()."
                    )
            elif pattern in lowered:
                raise ValueError(f"Disallowed pattern detected in code: {pattern}")

        # Load CSV once - this is what LLM will use
        df = pd.read_csv(self.csv_path)

        allowed_modules = {"pandas": pd, "numpy": np, "pd": pd, "np": np}

        def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in allowed_modules:
                return allowed_modules[name]
            raise ImportError(f"Import of module '{name}' is not allowed.")

        safe_builtins = {
            "len": len,
            "range": range,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "__import__": limited_import,
            # Add type constructors for data conversion
            "float": float,
            "int": int,
            "str": str,
            "bool": bool,
            # Add exception types for error handling
            "FileNotFoundError": FileNotFoundError,
            "ValueError": ValueError,
            "KeyError": KeyError,
            "TypeError": TypeError,
            "AttributeError": AttributeError,
            "IndexError": IndexError,
        }

        globals_env: Dict[str, Any] = {
            "__builtins__": safe_builtins,
            "pd": pd,
            "np": np,
            "CSV_PATH": str(self.csv_path),  # Keep for backward compatibility
        }
        locals_env: Dict[str, Any] = {
            "df": df.copy(),  # Pre-loaded dataframe - LLM should use this
        }

        exec(compile(code, "<unit_selector>", "exec"), globals_env, locals_env)

        # Check both locals and globals for result
        selected_df = None
        for candidate in self._RESULT_CANDIDATES:
            # Check locals first
            value = locals_env.get(candidate)
            if isinstance(value, pd.DataFrame):
                selected_df = value
                break
            # Check globals if not found in locals
            value = globals_env.get(candidate)
            if isinstance(value, pd.DataFrame):
                selected_df = value
                break

        if selected_df is None:
            available_vars = list(locals_env.keys()) + list(globals_env.keys())
            raise ValueError(
                f"Generated code did not produce a pandas DataFrame. "
                f"Expected one of: {', '.join(self._RESULT_CANDIDATES)}. "
                f"Available variables: {available_vars}"
            )

        if selected_df.empty:
            return []

        selected_df = selected_df.replace({np.nan: None})
        # Use provided max_rows if given, otherwise use self.max_rows
        limit = max_rows if max_rows is not None else self.max_rows
        result_df = selected_df.head(limit)

        return result_df.to_dict(orient="records")

    def _match_explicit_units(
        self,
        text_source: Optional[str],
        max_rows: Optional[int]
    ) -> Optional[List[Dict[str, Any]]]:
        """Return direct matches when question references specific unit codes/IDs."""
        if not text_source or self._df_cache.empty:
            return None

        compact = re.sub(r"\s+", "", text_source.lower())
        code_pattern = re.compile(r"([a-z0-9]+/[a-z0-9]+/[a-z0-9]+/[a-z0-9]+)", re.IGNORECASE)
        explicit_codes = {match.group(1) for match in code_pattern.finditer(compact)}

        number_pattern = re.compile(
            r"(?:كود|code|id|رقم)\s*(?:وحدة|شقة|الشقة|الشقه|#|بتاعها|هو|هي|:)?\s*(\d{2,})",
            re.IGNORECASE,
        )
        # Extract numeric IDs from the provided text source (question and/or history)
        explicit_numbers = {
            match.group(1).lstrip("0") or match.group(1)
            for match in number_pattern.finditer(text_source)
        }
        
        # Also extract standalone numbers (2+ digits) that might be unit IDs
        # This helps when additional message contains just numbers like "203"
        standalone_number_pattern = re.compile(r"\b(\d{2,})\b")
        standalone_numbers = {
            match.group(1).lstrip("0") or match.group(1)
            for match in standalone_number_pattern.finditer(text_source)
        }
        # Merge both sets
        explicit_numbers = explicit_numbers.union(standalone_numbers)

        if not explicit_codes and not explicit_numbers:
            return None

        mask = pd.Series(False, index=self._df_cache.index)
        if explicit_codes and not self._normalized_codes.empty:
            normalized_targets = {code.lower() for code in explicit_codes}
            mask |= self._normalized_codes.isin(normalized_targets)
        if explicit_numbers:
            if not self._name_strings.empty:
                mask |= self._name_strings.isin(explicit_numbers)
            if not self._normalized_codes.empty:
                endswith_patterns = tuple(f"/{num}" for num in explicit_numbers)
                mask |= self._normalized_codes.str.endswith(endswith_patterns)

        if not mask.any():
            return None

        limit = max_rows if max_rows is not None else self.max_rows
        matches = self._df_cache.loc[mask].head(limit)
        if matches.empty:
            return None
        return matches.replace({np.nan: None}).to_dict(orient="records")

    def _filter_within_last_units(
        self,
        question: str,
        last_units: List[Dict[str, Any]],
        max_rows: Optional[int]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Filter within last_units based on the question.
        Handles cases like "one of them on the second floor" or "the cheapest one of those".
        
        Args:
            question: User question
            last_units: List of previously selected units
            max_rows: Maximum number of rows to return
            
        Returns:
            Filtered list of units, or None if no filter applies
        """
        if not last_units:
            return None
        
        # Convert to DataFrame for easier filtering
        df_last = pd.DataFrame(last_units)
        if df_last.empty:
            return None
        
        # Simple heuristics for common filters within last_units
        lowered = question.lower()
        filtered_df = df_last.copy()
        filter_applied = False
        
        # Check for floor filters
        if "دور" in lowered or "floor" in lowered:
            if "تاني" in lowered or "2nd" in lowered or "ثاني" in lowered:
                if "Floor" in df_last.columns:
                    filtered_df = filtered_df[filtered_df["Floor"].astype(str).str.contains("2nd|ثاني|تاني", case=False, na=False)]
                    filter_applied = True
            elif "أول" in lowered or "1st" in lowered:
                if "Floor" in df_last.columns:
                    filtered_df = filtered_df[filtered_df["Floor"].astype(str).str.contains("1st|أول", case=False, na=False)]
                    filter_applied = True
            elif "ثالث" in lowered or "3rd" in lowered or "تالت" in lowered:
                if "Floor" in df_last.columns:
                    filtered_df = filtered_df[filtered_df["Floor"].astype(str).str.contains("3rd|ثالث|تالت", case=False, na=False)]
                    filter_applied = True
            elif "أرضي" in lowered or "ground" in lowered or "gr" in lowered:
                if "Floor" in df_last.columns:
                    filtered_df = filtered_df[filtered_df["Floor"].astype(str).str.contains("Gr|ground|أرضي", case=False, na=False)]
                    filter_applied = True
        
        # Check for price filters (cheapest/most expensive within last_units)
        if "أرخص" in lowered or "cheapest" in lowered or "أقل" in lowered:
            if "Price" in filtered_df.columns:
                try:
                    prices = pd.to_numeric(filtered_df["Price"], errors='coerce')
                    min_price = prices.min()
                    filtered_df = filtered_df[prices == min_price]
                    filter_applied = True
                except:
                    pass
        elif "أغلى" in lowered or "expensive" in lowered or "أعلى" in lowered:
            if "Price" in filtered_df.columns:
                try:
                    prices = pd.to_numeric(filtered_df["Price"], errors='coerce')
                    max_price = prices.max()
                    filtered_df = filtered_df[prices == max_price]
                    filter_applied = True
                except:
                    pass
        
        # Check for specific count requests (e.g., "one of them", "three of them")
        requested_count = self._extract_requested_count(question)
        if requested_count and requested_count < len(filtered_df):
            # If asking for specific count, sort by price (ascending) and take top N
            if "Price" in filtered_df.columns:
                try:
                    prices = pd.to_numeric(filtered_df["Price"], errors='coerce')
                    filtered_df = filtered_df.loc[prices.sort_values().head(requested_count).index]
                    filter_applied = True
                except:
                    filtered_df = filtered_df.head(requested_count)
                    filter_applied = True
            else:
                filtered_df = filtered_df.head(requested_count)
                filter_applied = True
        
        # If no filter was applied (filtered_df same as original), return None
        if not filter_applied or len(filtered_df) == len(df_last):
            return None
        
        # If filter resulted in empty, return None
        if filtered_df.empty:
            return None
        
        limit = max_rows if max_rows is not None else self.max_rows
        result = filtered_df.head(limit).replace({np.nan: None}).to_dict(orient="records")
        return result if result else None

    def _refers_to_history(self, question: str) -> bool:
        """Enhanced heuristic to detect pronoun-based references to previous turns."""
        if not question:
            return False
        lowered = question.lower()
        reference_phrases = [
            "الشقة اللي قولتلك",
            "الوحدة اللي قولتلك",
            "اللي قولتلك عليها",
            "اللي قولتلك عليه",
            "الكود بتاعها",
            "الكود بتاعه",
            "نفس الشقة",
            "نفس الوحدة",
            "دي اللي قولتلك عليها",
            "دي اللي قلتلك عليها",
            "نفسها",
            "زي ما قلت",
            "دول",
            "دي",
            "اللي فاتوا",
            "اللي قولت",
            "اللي قلت",
            "منهم",
            "واحدة منهم",
            "شقة منهم",
            "الفيلا دي",
            "الفيلا ديت",
            "الشقة دي",
            "الشقة ديت",
            "الوحدة دي",
            "الوحدة ديت",
            "الهبله دي",
            "الهبله ديت",
            "الوحده دي",
            "الوحده ديت",
            "عن الوحده",
            "عن الشقة",
            "عن الفيلا",
            "الوحده",
            "الشقة",
            "الفيلا",
        ]
        pronoun_hits = any(phrase in lowered for phrase in reference_phrases)

        # Check for payment/installment queries that likely refer to previously mentioned units
        payment_keywords = [
            "سداد", "دفع", "قسط", "payment", "installment", 
            "السداد", "الدفع", "القسط", "خريطة", "خريطه",
            "طرق السداد", "طرق الدفع", "خطة السداد", "خطة الدفع"
        ]
        has_payment_keyword = any(keyword in lowered for keyword in payment_keywords)
        
        # If query has payment keywords, it's likely referring to a previous unit
        if has_payment_keyword:
            pronoun_hits = True
            logger.debug("Detected payment/installment query - likely refers to previous unit: %s", question[:50])
        
        # If query has payment keywords and references "this/that" unit, it's definitely a follow-up
        if has_payment_keyword and any(word in lowered for word in ["دي", "ديت", "ديها", "this", "that", "the", "عن"]):
            pronoun_hits = True
            logger.debug("Detected payment/installment query with explicit reference: %s", question[:50])

        # Very short queries (< 30 chars) with payment keywords are likely follow-ups
        if not pronoun_hits and len(question.strip()) < 30 and has_payment_keyword:
            pronoun_hits = True
            logger.debug("Short payment query detected as follow-up: %s", question[:50])

        # Also treat very short questions with no numbers as likely references.
        if not pronoun_hits and len(question.strip()) < 25 and not re.search(r"\d", question):
            pronoun_hits = True

        return pronoun_hits


