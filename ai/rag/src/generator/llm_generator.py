"""
LLM Generator Module using Gemini API
Generates responses using Google's Gemini API.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Optional module-level handle for google.generativeai.
# This is primarily here so that unit tests can patch `genai`
# (e.g. `patch("src.generator.llm_generator.genai")`) without
# importing the real library.
try:  # pragma: no cover - simple import shim
    import google.generativeai as genai  # type: ignore
except Exception:  # ImportError or any environment issue
    genai = None  # type: ignore


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
        global genai  # use the module-level symbol so tests can patch it

        if genai is None:
            try:
                import google.generativeai as genai_lib  # type: ignore
            except ImportError as exc:  # pragma: no cover - exercised in envs without the lib
                raise ImportError(
                    "google-generativeai is required. Install it with: pip install google-generativeai"
                ) from exc
            genai = genai_lib  # type: ignore

        genai.configure(api_key=self.api_key)  # type: ignore[attr-defined]
        # In production this is a real GenerativeModel; in tests it's a Mock.
        self.client = genai.GenerativeModel(self.model_name)  # type: ignore[attr-defined]
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
            # Build a simple dict for generation config instead of relying on
            # the concrete google.generativeai.GenerationConfig type. This
            # makes unit testing easier and is all the mocked client needs.
            generation_config: Dict[str, Any] = {"temperature": temperature, **kwargs}
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens

            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config,
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
            full_prompt = f"""أنت مستشار عقاري محترف تخاطب العميل باللهجة المصرية لكن بنبرة رسمية ومحترمة توحي بالثقة والخبرة.

**تصحيح تلقائي للاستفسار:**
قبل الإجابة، قم بتصحيح الأخطاء الإملائية الشائعة تلقائياً:
- أخطاء شائعة: 'شهور' → 'شقق'، 'عجلات' → 'شقق'، 'موديلات' → 'شقق'، 'موبايلات' → 'شقق'
- كلمات ناقصة: 'ثلاثه' → 'ثلاثة'، 'ثلاث' → 'ثلاثة'، 'ارخص' → 'أرخص'
- اختلافات: 'فيلا' = 'فيله'، 'شقة' = 'شقه' = 'شقق'
- أخطاء إملائية: 'السادات' → 'السداد' (خطة السداد)، 'الهبله' → 'الفيلا'
- إزالة المسافات الزائدة وتوحيد علامات الترقيم
قم بتطبيق هذه التصحيحات تلقائياً عند فهم الاستفسار.

**تعليمات أسلوبية وسياقية:**
1. استخدم لهجة مصرية واضحة لكن بصياغة رسمية/خدمية (زي خدمة عملاء راقية): جُمل مرتبة، مفردات مهذبة، بدون هزار أو تعبيرات مبالغ فيها.
2. اذكر الحقائق بدقة، واشرح الخطوات أو الخيارات بشكل منظم (قوائم قصيرة أو جمل مرقمة عند الحاجة).
3. اعتمد فقط على المعلومات الموجودة في الأقسام التالية؛ لو المعلومة مش متاحة، قل ذلك بنبرة رسمية: "للأسف المعلومة دي مش موجودة حالياً في بياناتنا".
4. اربط إجابتك بالأسئلة السابقة لو التاريخ موجود، ووضح أي استنتاج مبني على محادثة سابقة.
5. عندما تتوفر بيانات منظمة للوحدات (structured units) أو أوصاف نصية للوحدة (Description)، التزم بالآتي:
   - اقرأ وصف كل وحدة جيداً واستخرج منه خصائص الوحدة: الموقع، عدد الغرف، المساحة، الدور، الإطلالة (بحر/حمام سباحة/جاردن/شارع)، حالة التشطيب، وجود فرش، خطة السداد، ونوع الوحدة (شقة، فيلا، دوبلكس، ستوديو، ..).
   - لو الوصف يذكر مميزات خاصة (بحري، قريبة من البحر، على محور رئيسي، مطلة على لاجون، قرب الخدمات، مساحات خارجية مثل جاردن أو روف)، وضّح هذه المميزات للعميل في الرد.
   - اعرض الوحدات في قائمة مرقمة (1، 2، 3...) مع الكود، السعر، المساحة، الدور، النوع، وأهم الخصائص المستخرجة من الوصف باختصار.
   - لا تخترع وحدات أو أكواد أو خصائص غير مذكورة في البيانات أو الوصف؛ يمكنك فقط الاستنتاج المنطقي المباشر من النص (مثلاً: \"غرفة ماستر\" ⇒ يوجد حمام خاص داخل الغرفة).
   - لو السؤال عن \"أرخص\" أو \"أغلى\" أو \"٣ وحدات\" استخدم ترتيب واضح حسب السعر أو المعايير المطلوبة، واذكر سبب الاختيار (مثلاً: دي أقل سعر للمساحة المطلوبة).
6. لو لم توجد أي وحدات منظمة أو أوصاف مناسبة للسؤال، كن صريحاً: لا تخترع أرقام أو وحدات، واطلب من العميل توضيح الكود أو المعايير لو السؤال غامض.
7. اختصر قدر الإمكان بدون فقدان الدقة، وانهِ الرد بعرض مساعدة إضافية عند اللزوم.

{history_section}{context_section}{structured_section}**سؤال المستخدم الحالي:**
{prompt}

**ردك الرسمي باللهجة المصرية:**"""
        else:
            # Even without context, keep the professional Egyptian tone
            full_prompt = f"""أنت مستشار عقاري محترف. أجب على السؤال التالي باللهجة المصرية ولكن بصياغة رسمية ومحترفة، مع التركيز على الدقة والوضوح.

**تصحيح تلقائي للاستفسار:**
قبل الإجابة، قم بتصحيح الأخطاء الإملائية الشائعة تلقائياً:
- أخطاء شائعة: 'شهور' → 'شقق'، 'عجلات' → 'شقق'، 'موديلات' → 'شقق'، 'موبايلات' → 'شقق'
- كلمات ناقصة: 'ثلاثه' → 'ثلاثة'، 'ثلاث' → 'ثلاثة'، 'ارخص' → 'أرخص'
- اختلافات: 'فيلا' = 'فيله'، 'شقة' = 'شقه' = 'شقق'
- أخطاء إملائية: 'السادات' → 'السداد' (خطة السداد)، 'الهبله' → 'الفيلا'
- إزالة المسافات الزائدة وتوحيد علامات الترقيم
قم بتطبيق هذه التصحيحات تلقائياً عند فهم الاستفسار.

السؤال: {prompt}

الرد الرسمي باللهجة المصرية:"""
        
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
            bedrooms = row.get("Bedrooms") or row.get("bedrooms") or ""
            bathrooms = row.get("Bathrooms") or row.get("bathrooms") or ""
            garden = row.get("Garden") or row.get("garden") or ""
            roof = row.get("Roof") or row.get("roof") or ""
            description = row.get("Description") or row.get("description") or ""

            snippet = f"- الكود: {code} | السعر: {price} | المساحة: {area}"
            if usage:
                snippet += f" | النوع: {usage}"
            if floor:
                snippet += f" | الدور: {floor}"
            if project:
                snippet += f" | المشروع: {project}"
            if bedrooms:
                snippet += f" | غرف: {bedrooms}"
            if bathrooms:
                snippet += f" | حمامات: {bathrooms}"
            # Highlight outdoor spaces briefly
            extra_features = []
            if garden:
                extra_features.append("جاردن")
            if roof:
                extra_features.append("روف")
            if extra_features:
                snippet += " | مميزات خارجية: " + " + ".join(extra_features)

            # Add a short trimmed description so the model can infer more properties
            if description:
                short_desc = str(description).strip()
                if len(short_desc) > 220:
                    short_desc = short_desc[:220].rstrip() + "..."
                snippet += f"\n  وصف مختصر: {short_desc}"

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
            generation_config: Dict[str, Any] = {"temperature": temperature, **kwargs}

            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config,
                stream=True,
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

