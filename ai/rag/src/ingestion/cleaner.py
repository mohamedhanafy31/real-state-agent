"""
Arabic Text Cleaner Module
Preprocessing and normalization for Egyptian dialect Arabic text.
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class TextCleaner:
    """Cleans and normalizes Arabic text, especially Egyptian dialect."""
    
    def __init__(self):
        # Arabic diacritics pattern
        self.diacritics_pattern = re.compile(r'[\u064B-\u065F\u0670]')
        
        # Tatweel (elongation) pattern
        self.tatweel_pattern = re.compile(r'ـ+')
        
        # Multiple spaces pattern
        self.multiple_spaces_pattern = re.compile(r'\s+')
        
        # Multiple newlines pattern
        self.multiple_newlines_pattern = re.compile(r'\n{3,}')
        
        # Egyptian dialect specific replacements
        self.egyptian_replacements = {
            # Common Egyptian dialect variations
            'إيه': 'إي',
            'ايه': 'إي',
            'ازيك': 'كيف حالك',
            'ازي': 'كيف',
            'عايز': 'أريد',
            'عاوز': 'أريد',
            'عايزة': 'أريد',
            'عاوزة': 'أريد',
            'عندك': 'لديك',
            'عندي': 'لدي',
            'عنده': 'لديه',
            'عندها': 'لديها',
            'عندنا': 'لدينا',
            'عندكم': 'لديكم',
            'عندهم': 'لديهم',
            'مش': 'ليس',
            'مفيش': 'لا يوجد',
            'في': 'يوجد',
            'فيه': 'يوجد',
            'فيها': 'يوجد',
            'فينا': 'يوجد',
            'فيكم': 'يوجد',
            'فيهم': 'يوجد',
            # Future tense (Egyptian dialect)
            'هقول': 'سأقول',
            'هروح': 'سأذهب',
            'هجيب': 'سأحضر',
            'هعمل': 'سأعمل',
            'هشوف': 'سأرى',
            'هسمع': 'سأسمع',
            'هاخد': 'سآخذ',
            'هعرف': 'سأعرف',
            'هفهم': 'سأفهم',
            'هحاول': 'سأحاول',
            'هبدأ': 'سأبدأ',
            'هخلص': 'سأنهي',
            'هكمل': 'سأكمل',
            'هعدل': 'سأعدل',
            'هغير': 'سأغير',
            'هضيف': 'سأضيف',
            'هحذف': 'سأحذف',
            'هفتح': 'سأفتح',
            'هقفل': 'سأقفل',
            'هشغل': 'سأشغل',
            'هوقف': 'سأوقف',
            'هشيل': 'سأزيل',
            'هحط': 'سأضع',
            'هجرب': 'سأجرب',
            'هحفظ': 'سأحفظ',
            'هطبع': 'سأطبع',
            'هبعت': 'سأرسل',
            'هستقبل': 'سأستقبل',
            'هرد': 'سأرد',
            'هتكلم': 'سأتحدث',
        }
    
    def clean(self, text: str, remove_diacritics: bool = True, 
              normalize_egyptian: bool = True, 
              remove_tatweel: bool = True) -> str:
        """
        Clean and normalize Arabic text.
        
        Args:
            text: Input Arabic text
            remove_diacritics: Whether to remove Arabic diacritics
            normalize_egyptian: Whether to normalize Egyptian dialect
            remove_tatweel: Whether to remove tatweel (elongation marks)
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove diacritics
        if remove_diacritics:
            text = self.diacritics_pattern.sub('', text)
        
        # Remove tatweel
        if remove_tatweel:
            text = self.tatweel_pattern.sub('', text)
        
        # Normalize Egyptian dialect
        if normalize_egyptian:
            text = self._normalize_egyptian_dialect(text)
        
        # Normalize Arabic characters
        text = self._normalize_arabic_chars(text)
        
        # Remove extra whitespace
        text = self.multiple_spaces_pattern.sub(' ', text)
        text = self.multiple_newlines_pattern.sub('\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _normalize_egyptian_dialect(self, text: str) -> str:
        """Normalize Egyptian dialect to Modern Standard Arabic."""
        # Sort by length (longest first) to avoid partial replacements
        sorted_replacements = sorted(
            self.egyptian_replacements.items(), 
            key=lambda x: len(x[0]), 
            reverse=True
        )
        
        for dialect, msa in sorted_replacements:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(dialect) + r'\b'
            text = re.sub(pattern, msa, text)
        
        return text
    
    def _normalize_arabic_chars(self, text: str) -> str:
        """Normalize Arabic characters."""
        # Normalize Alef variations
        text = re.sub(r'[إأآا]', 'ا', text)
        
        # Normalize Teh Marbuta
        text = re.sub(r'ة', 'ه', text)
        
        # Normalize Yeh variations (keep final Yeh as is)
        # This is more complex and context-dependent, so we'll be conservative
        text = re.sub(r'[يى]', 'ي', text)
        
        return text
    
    def clean_batch(self, texts: List[str], **kwargs) -> List[str]:
        """Clean a batch of texts."""
        return [self.clean(text, **kwargs) for text in texts]

