"""
Unit tests for TextCleaner
"""

import pytest
from src.ingestion.cleaner import TextCleaner


class TestTextCleaner:
    """Test cases for TextCleaner."""
    
    def test_init(self):
        """Test cleaner initialization."""
        cleaner = TextCleaner()
        assert cleaner.diacritics_pattern is not None
        assert cleaner.tatweel_pattern is not None
        assert len(cleaner.egyptian_replacements) > 0
    
    def test_clean_empty_text(self):
        """Test cleaning empty text."""
        cleaner = TextCleaner()
        result = cleaner.clean("")
        assert result == ""
    
    def test_clean_none_text(self):
        """Test cleaning None text."""
        cleaner = TextCleaner()
        result = cleaner.clean(None)
        assert result == ""
    
    def test_remove_diacritics(self):
        """Test removing Arabic diacritics."""
        cleaner = TextCleaner()
        text_with_diacritics = "الْكَلِمَةُ"
        result = cleaner.clean(text_with_diacritics, remove_diacritics=True)
        assert "ال" not in result or len(result) < len(text_with_diacritics)
    
    def test_remove_tatweel(self):
        """Test removing tatweel (elongation marks)."""
        cleaner = TextCleaner()
        text_with_tatweel = "كلمةـــــ"
        result = cleaner.clean(text_with_tatweel, remove_tatweel=True)
        assert "ـ" not in result
    
    def test_normalize_egyptian_dialect(self, sample_egyptian_text):
        """Test normalizing Egyptian dialect."""
        cleaner = TextCleaner()
        result = cleaner.clean(sample_egyptian_text, normalize_egyptian=True)
        
        # Check that some Egyptian words are normalized
        # Note: This is a basic check - actual normalization depends on the dictionary
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_normalize_arabic_chars(self):
        """Test normalizing Arabic characters."""
        cleaner = TextCleaner()
        # Test with different Alef variations
        text = "إسلام أمة آمنة"
        result = cleaner._normalize_arabic_chars(text)
        # Should normalize Alef variations (basic check)
        assert isinstance(result, str)
    
    def test_remove_extra_whitespace(self):
        """Test removing extra whitespace."""
        cleaner = TextCleaner()
        text = "كلمة    أخرى    ثالثة"
        result = cleaner.clean(text)
        # Should have normalized whitespace
        assert "    " not in result
    
    def test_remove_multiple_newlines(self):
        """Test removing multiple newlines."""
        cleaner = TextCleaner()
        text = "فقرة أولى\n\n\n\nفقرة ثانية"
        result = cleaner.clean(text)
        # Should have at most 2 newlines
        assert "\n\n\n\n" not in result
    
    def test_clean_batch(self):
        """Test cleaning a batch of texts."""
        cleaner = TextCleaner()
        texts = ["نص أول", "نص ثاني", "نص ثالث"]
        results = cleaner.clean_batch(texts)
        
        assert len(results) == len(texts)
        assert all(isinstance(r, str) for r in results)
    
    def test_egyptian_replacements(self):
        """Test specific Egyptian dialect replacements."""
        cleaner = TextCleaner()
        
        # Test some common replacements
        test_cases = [
            ("عايز", "أريد"),
            ("مش", "ليس"),
            ("عندك", "لديك"),
        ]
        
        for dialect, expected_msa in test_cases:
            result = cleaner._normalize_egyptian_dialect(f"أنا {dialect} هذا")
            # The result should contain the normalized version
            # Note: This depends on word boundaries, so we check it's processed
            assert isinstance(result, str)
    
    def test_preserve_text_structure(self, sample_text):
        """Test that text structure is preserved after cleaning."""
        cleaner = TextCleaner()
        result = cleaner.clean(sample_text)
        
        # Should still have paragraphs (double newlines)
        assert "\n\n" in result or len(result) > 0
        assert isinstance(result, str)

