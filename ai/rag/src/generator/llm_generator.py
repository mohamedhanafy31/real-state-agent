"""
LLM Generator Module using Gemini API
Generates responses using Google's Gemini API.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LLMGenerator:
    """Generator using Google's Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the Gemini generator.
        
        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
            model_name: Name of the Gemini model to use
        """
        self.model_name = model_name
        
        # Get API key
        if api_key is None:
            api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.api_key = api_key
        
        # Initialize Gemini client
        self._init_client()
    
    def _init_client(self):
        """Initialize the Gemini API client."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai is required. Install it with: pip install google-generativeai"
            )
        
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model_name)
        logger.info(f"Initialized Gemini client with model: {self.model_name}")
    
    def generate(self, prompt: str, context: Optional[List[str]] = None,
                conversation_history: Optional[str] = None,
                structured_data: Optional[List[Dict[str, Any]]] = None,
                temperature: float = 0.7, max_tokens: Optional[int] = None,
                **kwargs) -> str:
        """
        Generate a response using Gemini API.
        
        Args:
            prompt: User query/prompt
            context: Optional list of context chunks from retrieval
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Returns:
            Generated response text
        """
        # Build the full prompt with context, history, and structured data
        full_prompt = self._build_prompt(
            prompt,
            context,
            conversation_history,
            structured_data=structured_data,
        )
        
        try:
            import google.generativeai as genai
            
            # Prepare generation config with thinking disabled
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                **kwargs
            )
            
            if max_tokens:
                generation_config.max_output_tokens = max_tokens
            
            # Disable thinking/reasoning if the model supports it
            # This prevents the model from showing intermediate reasoning steps
            try:
                # Try to disable thinking_config if available
                if hasattr(generation_config, 'thinking_config'):
                    generation_config.thinking_config = None
            except (AttributeError, TypeError):
                # If thinking_config is not available, that's fine
                pass
            
            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            # Extract only the final answer, skip any thinking/reasoning text
            text = response.text
            
            # Additional filtering: Remove common thinking markers if present
            # Some models might still include reasoning even with thinking disabled
            thinking_markers = [
                "Let me think",
                "دعني أفكر",
                "Thinking:",
                "Reasoning:",
                "المنطق:"
            ]
            
            # If the response starts with thinking markers, try to extract the actual answer
            for marker in thinking_markers:
                if text.startswith(marker) or text.lower().startswith(marker.lower()):
                    # Try to find the actual answer after thinking
                    parts = text.split('\n\n', 1)
                    if len(parts) > 1:
                        text = parts[-1]  # Take the last part as the answer
                    break
            
            return text
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise
    
    def _build_prompt(self, prompt: str, context: Optional[List[str]] = None, 
                     conversation_history: Optional[str] = None,
                     structured_data: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Build the full prompt with context and conversation history.
        
        Args:
            prompt: Current user question
            context: Optional list of context chunks from retrieval
            conversation_history: Optional conversation history string
        """
        # Build context section
        context_section = ""
        if context:
            context_text = "\n\n".join([
                f"[معلومة {i+1}]:\n{chunk}" 
                for i, chunk in enumerate(context)
            ])
            context_section = f"""**المعلومات المتاحة:**
{context_text}

"""
        
        # Build conversation history section
        history_section = ""
        if conversation_history:
            history_section = f"""**تاريخ المحادثة السابق:**
{conversation_history}

"""
        
        structured_section = ""
        if structured_data:
            structured_section = self._format_structured_data(structured_data)

        # Build full prompt - optimized for interactive Egyptian dialect chatbot
        if context or conversation_history or structured_section:
            full_prompt = f"""أنت مساعد ذكي ومفيد متخصص في العقارات والخدمات. مهمتك هي مساعدة المستخدمين بطريقة ودودة ومحادثة.

**تعليمات مهمة:**
1. أجب باللهجة المصرية بشكل طبيعي ومحادثة (مثل: "إيه اللي محتاجه؟"، "عندنا كذا وكذا")
2. كن تفاعلي وودود - استخدم أسلوب محادثة طبيعي
3. استخدم المعلومات المرفقة فقط للإجابة
4. إذا لم تجد الإجابة في المعلومات المرفقة، قل ذلك بوضوح باللهجة المصرية (مثل: "للأسف مش لاقي المعلومة دي في البيانات بتاعتنا")
5. كن مختصر ومباشر، لكن ودود
6. استخدم أمثلة من المعلومات المرفقة عند الإجابة
7. لو فيه بيانات منظمة للوحدات (جداول) اعرض أهم التفاصيل بالأرقام المتاحة
8. استخدم تاريخ المحادثة السابق لفهم السياق والإجابة بشكل متسق

{history_section}{context_section}{structured_section}**سؤال المستخدم الحالي:**
{prompt}

**ردك (باللهجة المصرية):**"""
        else:
            # Even without context, make it interactive and in Egyptian dialect
            full_prompt = f"""أنت مساعد ذكي ومفيد. أجب على السؤال التالي باللهجة المصرية بشكل طبيعي ومحادثة ودود.

السؤال: {prompt}

الرد:"""
        
        return full_prompt

    def _format_structured_data(self, structured_data: List[Dict[str, Any]]) -> str:
        """Convert structured unit rows into a concise Arabic snippet."""
        if not structured_data:
            return ""

        lines = []
        for row in structured_data[:5]:
            code = row.get("Code") or row.get("code") or "غير محدد"
            price = row.get("Price") or row.get("price") or "غير متاح"
            area = row.get("Area") or row.get("area") or "غير متاح"
            usage = row.get("Usage") or row.get("usage") or ""
            project = row.get("Project") or row.get("project") or ""
            floor = row.get("Floor") or row.get("floor") or ""
            snippet = f"- الكود: {code} | السعر: {price} | المساحة: {area}"
            if usage:
                snippet += f" | النوع: {usage}"
            if floor:
                snippet += f" | الدور: {floor}"
            if project:
                snippet += f" | المشروع: {project}"
            lines.append(snippet)

        formatted = "\n".join(lines)
        return f"""**وحدات مطابقة من جدول الأسعار:**
{formatted}

"""
    
    def generate_stream(self, prompt: str, context: Optional[List[str]] = None,
                       conversation_history: Optional[str] = None,
                       structured_data: Optional[List[Dict[str, Any]]] = None,
                       temperature: float = 0.7, **kwargs):
        """
        Generate a streaming response.
        
        Args:
            prompt: User query/prompt
            context: Optional list of context chunks
            temperature: Sampling temperature
            **kwargs: Additional generation parameters
            
        Yields:
            Response chunks as they are generated
        """
        full_prompt = self._build_prompt(
            prompt,
            context,
            conversation_history,
            structured_data=structured_data,
        )
        
        try:
            import google.generativeai as genai
            
            # Prepare generation config with thinking disabled
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                **kwargs
            )
            
            # Disable thinking/reasoning if the model supports it
            try:
                if hasattr(generation_config, 'thinking_config'):
                    generation_config.thinking_config = None
            except (AttributeError, TypeError):
                pass
            
            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config,
                stream=True
            )
            
            # Filter out thinking markers from streamed chunks
            thinking_markers = [
                "Let me think",
                "دعني أفكر",
                "Thinking:",
                "Reasoning:",
                "المنطق:"
            ]
            
            for chunk in response:
                if chunk.text:
                    text = chunk.text
                    # Skip chunks that are clearly thinking markers
                    skip = False
                    for marker in thinking_markers:
                        if marker.lower() in text.lower() and len(text.strip()) < 50:
                            skip = True
                            break
                    if not skip:
                        yield text
                        
        except Exception as e:
            logger.error(f"Error in streaming generation: {str(e)}")
            raise

