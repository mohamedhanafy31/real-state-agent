"""
RAG Pipeline Evaluation Script
Tests the RAG system with questions and expected answers based on TransIT Profile document.
"""

import os
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from rag_graph.main import run_query
from src.utils import setup_run_logging, get_logger, load_config, get_config_value
from src.embeddings import AraModernBERTEmbedder

# Setup logging
run_logger = setup_run_logging(
    run_name=f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    log_dir=os.getenv('LOG_DIR', 'logs'),
    level=os.getenv('LOG_LEVEL', 'INFO')
)

logger = get_logger(__name__)


# Test Questions and Expected Answers (Egyptian Dialect)
TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "إيه هي شركة ترانس آي تي؟",
        "expected_keywords": ["ترانس آي تي", "Trans IT", "تكنولوجيا معلومات", "2007", "هيئة سكك حديد مصر"],
        "category": "company_info"
    },
    {
        "id": 2,
        "question": "متى اتأسست الشركة وإيه اللي ملكها؟",
        "expected_keywords": ["2007", "هيئة سكك حديد مصر", "مملوكة بالكامل"],
        "category": "company_info"
    },
    {
        "id": 3,
        "question": "فين مقر الشركة؟",
        "expected_keywords": ["مبنى الحاسب الآلي", "هيئة سكك حديد مصر", "محطة مصر", "ميدان أحمد حلمي"],
        "category": "company_info"
    },
    {
        "id": 4,
        "question": "إيه الهيكل التنظيمي للشركة؟",
        "expected_keywords": ["رئيس مجلس الإدارة", "العضو المنتدب", "قطاعات", "التكنولوجيا", "النظم والتطبيقات", "التطوير"],
        "category": "company_structure"
    },
    {
        "id": 5,
        "question": "إيه إنجازات الشركة؟",
        "expected_keywords": ["238 مليون جنيه", "2008", "2016", "مراكز بيانات", "Data Center", "شبكات"],
        "category": "achievements"
    },
    {
        "id": 6,
        "question": "الشركة عملت إيه في مشروعات هيئة سكك حديد مصر؟",
        "expected_keywords": ["238 مليون جنيه", "أنظمة حجز التذاكر", "ERP", "شحن البضائع", "الدفع الإلكتروني"],
        "category": "achievements"
    },
    {
        "id": 7,
        "question": "الشركة بتشارك في إيه من المشروعات القومية؟",
        "expected_keywords": ["التحول الرقمي", "الكارت الذكي", "التذكرة الموحدة", "معارض Trans Mea"],
        "category": "achievements"
    },
    {
        "id": 8,
        "question": "إيه هو تطبيق الموارد البشرية؟",
        "expected_keywords": ["تطبيق الموارد البشرية", "HR App", "إدارة الموارد البشرية", "قاعدة بيانات"],
        "category": "projects"
    },
    {
        "id": 9,
        "question": "تطبيق الموارد البشرية بيعمل إيه؟",
        "expected_keywords": ["إدارة الموارد البشرية", "المشروعات", "المشتريات", "السيارات", "التدريب", "نماذج إلكترونية"],
        "category": "projects"
    },
    {
        "id": 10,
        "question": "الشركة عندها شراكات مع مين؟",
        "expected_keywords": ["هواوي", "السويدي", "شركات عالمية"],
        "category": "partnerships"
    },
    {
        "id": 11,
        "question": "إيه رؤية الشركة وأهدافها؟",
        "expected_keywords": ["الخيار الأول", "وزارة النقل", "نظم المعلومات", "البنية التحتية", "الدعم الفني"],
        "category": "vision"
    },
    {
        "id": 12,
        "question": "الشركة بتعمل إيه في صيانة ماكينات التذاكر؟",
        "expected_keywords": ["صيانة", "تشغيل", "ماكينات إصدار التذاكر الذاتية", "TVM", "2010"],
        "category": "services"
    }
]


async def evaluate_rag_pipeline(
    questions: List[Dict[str, Any]],
    index_path: str = "data/embeddings/index.faiss",
    chunks_path: str = "data/embeddings/chunks.pkl",
    retrieval_k: int = 5
) -> Dict[str, Any]:
    """
    Evaluate the RAG pipeline with test questions.
    
    Args:
        questions: List of test questions with expected keywords
        index_path: Path to FAISS index
        chunks_path: Path to chunks file
        retrieval_k: Number of chunks to retrieve
        
    Returns:
        Evaluation results dictionary
    """
    logger.info("=" * 80)
    logger.info("Starting RAG Pipeline Evaluation")
    logger.info("=" * 80)
    
    # Check if index exists
    if not Path(index_path).exists() or not Path(chunks_path).exists():
        logger.error(f"Index not found at {index_path} or {chunks_path}")
        logger.error("Please run ingestion first: python run.py ingest")
        return {
            "error": "Index not found. Please run ingestion first.",
            "total_questions": len(questions),
            "results": []
        }
    
    # Load embedder (preloaded if available)
    config = load_config("config/settings.yaml")
    model_name = get_config_value(config, 'embedding.model_name', 'mohamed2811/Muffakir_Embedding_V2')
    device = get_config_value(config, 'embedding.device', None)
    if device is None:
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    logger.info(f"Loading embedder: {model_name} on {device}")
    embedder = AraModernBERTEmbedder(model_name=model_name, device=device)
    embedding_dim = embedder.get_embedding_dim()
    logger.info(f"Embedder loaded. Dimension: {embedding_dim}")
    
    results = []
    correct_answers = 0
    total_keywords_found = 0
    total_keywords_expected = 0
    
    for i, test_case in enumerate(questions, 1):
        logger.info("")
        logger.info("-" * 80)
        logger.info(f"Question {i}/{len(questions)}: {test_case['question']}")
        logger.info("-" * 80)
        
        try:
            # Run query - returns Answer object directly
            answer_obj = await run_query(
                question=test_case['question'],
                index_path=index_path,
                chunks_path=chunks_path,
                embedder=embedder,
                embedding_dim=embedding_dim,
                retrieval_k=retrieval_k
            )
            
            # Handle Answer object
            if answer_obj is None:
                logger.warning(f"No answer generated for question {i}")
                results.append({
                    "question_id": test_case['id'],
                    "question": test_case['question'],
                    "answer": None,
                    "expected_keywords": test_case['expected_keywords'],
                    "keywords_found": [],
                    "keywords_missing": test_case['expected_keywords'],
                    "score": 0.0,
                    "status": "failed"
                })
                continue
            
            # Extract text from Answer object
            if hasattr(answer_obj, 'text'):
                answer = answer_obj.text or ''
                retrieved_chunks = getattr(answer_obj, 'context_chunks', [])
            elif isinstance(answer_obj, str):
                answer = answer_obj
                retrieved_chunks = []
            else:
                # Try to get text from various attributes
                answer = getattr(answer_obj, 'content', getattr(answer_obj, 'text', str(answer_obj)))
                retrieved_chunks = getattr(answer_obj, 'context_chunks', getattr(answer_obj, 'retrieved_chunks', []))
            
            # Debug: log answer type and content
            logger.debug(f"Answer object type: {type(answer_obj)}")
            logger.debug(f"Answer text length: {len(answer) if answer else 0}")
            
            if not answer or len(answer.strip()) == 0:
                logger.warning(f"Empty answer for question {i}")
                results.append({
                    "question_id": test_case['id'],
                    "question": test_case['question'],
                    "answer": None,
                    "expected_keywords": test_case['expected_keywords'],
                    "keywords_found": [],
                    "keywords_missing": test_case['expected_keywords'],
                    "score": 0.0,
                    "status": "failed",
                    "error": "Empty answer"
                })
                continue
            
            # Check for expected keywords in answer
            answer_lower = answer.lower()
            keywords_found = []
            keywords_missing = []
            
            for keyword in test_case['expected_keywords']:
                keyword_lower = keyword.lower()
                if keyword_lower in answer_lower:
                    keywords_found.append(keyword)
                else:
                    keywords_missing.append(keyword)
            
            # Calculate score (percentage of keywords found)
            score = len(keywords_found) / len(test_case['expected_keywords']) if test_case['expected_keywords'] else 0.0
            total_keywords_found += len(keywords_found)
            total_keywords_expected += len(test_case['expected_keywords'])
            
            # Consider answer correct if at least 50% of keywords are found
            is_correct = score >= 0.5
            if is_correct:
                correct_answers += 1
            
            logger.info(f"Answer: {answer[:200]}...")
            logger.info(f"Keywords found: {len(keywords_found)}/{len(test_case['expected_keywords'])}")
            logger.info(f"Found: {keywords_found}")
            logger.info(f"Missing: {keywords_missing}")
            logger.info(f"Score: {score:.2%}")
            logger.info(f"Status: {'✓ PASS' if is_correct else '✗ FAIL'}")
            
            results.append({
                "question_id": test_case['id'],
                "question": test_case['question'],
                "answer": answer,
                "expected_keywords": test_case['expected_keywords'],
                "keywords_found": keywords_found,
                "keywords_missing": keywords_missing,
                "score": score,
                "status": "pass" if is_correct else "fail",
                "num_retrieved_chunks": len(retrieved_chunks),
                "category": test_case.get('category', 'unknown')
            })
            
        except Exception as e:
            logger.error(f"Error processing question {i}: {str(e)}", exc_info=True)
            results.append({
                "question_id": test_case['id'],
                "question": test_case['question'],
                "answer": None,
                "error": str(e),
                "status": "error"
            })
    
    # Calculate overall metrics
    overall_score = correct_answers / len(questions) if questions else 0.0
    keyword_accuracy = total_keywords_found / total_keywords_expected if total_keywords_expected > 0 else 0.0
    
    evaluation_summary = {
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(questions),
        "correct_answers": correct_answers,
        "overall_accuracy": overall_score,
        "keyword_accuracy": keyword_accuracy,
        "total_keywords_found": total_keywords_found,
        "total_keywords_expected": total_keywords_expected,
        "results": results
    }
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("EVALUATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Questions: {len(questions)}")
    logger.info(f"Correct Answers: {correct_answers}")
    logger.info(f"Overall Accuracy: {overall_score:.2%}")
    logger.info(f"Keyword Accuracy: {keyword_accuracy:.2%}")
    logger.info(f"Keywords Found: {total_keywords_found}/{total_keywords_expected}")
    logger.info("=" * 80)
    
    return evaluation_summary


def print_detailed_results(summary: Dict[str, Any]):
    """Print detailed evaluation results."""
    print("\n" + "=" * 80)
    print("DETAILED EVALUATION RESULTS")
    print("=" * 80)
    
    for result in summary['results']:
        print(f"\nQuestion {result['question_id']}: {result['question']}")
        print(f"Category: {result.get('category', 'unknown')}")
        print(f"Status: {result.get('status', 'unknown').upper()}")
        if result.get('answer'):
            print(f"Answer: {result['answer'][:300]}...")
            print(f"Score: {result.get('score', 0):.2%}")
            print(f"Keywords Found ({len(result.get('keywords_found', []))}): {result.get('keywords_found', [])}")
            print(f"Keywords Missing ({len(result.get('keywords_missing', []))}): {result.get('keywords_missing', [])}")
        else:
            print(f"Error: {result.get('error', 'No answer generated')}")
        print("-" * 80)


async def main():
    """Main evaluation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate RAG Pipeline")
    parser.add_argument("--index-path", type=str, default="data/embeddings/index.faiss",
                       help="Path to FAISS index")
    parser.add_argument("--chunks-path", type=str, default="data/embeddings/chunks.pkl",
                       help="Path to chunks file")
    parser.add_argument("--retrieval-k", type=int, default=5,
                       help="Number of chunks to retrieve")
    parser.add_argument("--output", type=str, default="evaluation_results.json",
                       help="Output file for results")
    parser.add_argument("--detailed", action="store_true",
                       help="Print detailed results")
    
    args = parser.parse_args()
    
    # Run evaluation
    summary = await evaluate_rag_pipeline(
        questions=TEST_QUESTIONS,
        index_path=args.index_path,
        chunks_path=args.chunks_path,
        retrieval_k=args.retrieval_k
    )
    
    # Save results to JSON
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\nResults saved to: {output_path}")
    
    # Print detailed results if requested
    if args.detailed:
        print_detailed_results(summary)
    
    return summary


if __name__ == "__main__":
    asyncio.run(main())

