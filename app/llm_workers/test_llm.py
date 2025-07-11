import os
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from app.llm_workers.processor.processor import URLProcessor
from app.llm_workers.evaluator.evaluator import URLProcessingEvaluator
from app.common.models import URLProcessingResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def setup_llm():
    """Initialize and return LLM instance"""
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        logger.error("GROQ_API_KEY not found in environment variables!")
        exit(1)

    try:
        llm_instance = ChatGroq(
            model="llama3-8b-8192",
            groq_api_key=api_key,
            temperature=0.3,
            max_tokens=512
        )
        logger.info("Groq LLM initialized successfully")
        return llm_instance
    except Exception as e:
        logger.exception("Error initializing Groq LLM")
        exit(1)

def test_processor():
    """Test the URL processor"""
    print("\n" + "="*60)
    print("TESTING URL PROCESSOR")
    print("="*60)
    
    llm = setup_llm()
    test_url = "https://en.wikipedia.org/wiki/OpenAI"
    
    try:
        processor = URLProcessor(llm)
        result = processor.process_url(test_url)
        processor.print_report(result)
        return result
    except Exception as e:
        logger.exception("Error testing processor")
        return None

def test_evaluator():
    """Test the URL evaluator with sample data"""
    print("\n" + "="*60)
    print("TESTING URL EVALUATOR")
    print("="*60)
    
    llm = setup_llm()
    
    # Sample data for testing
    sample_result = URLProcessingResult(
        url= "https://en.wikipedia.org/wiki/OpenAI",
        summary=(
            "OpenAI is a research organization founded in 2015 to advance artificial intelligence. "
            "The organization has developed AI models, partnered with major tech companies, and faced controversies "
            "over content moderation, military use, and transparency. The family of OpenAI whistleblower Suchir Balaji "
            "has filed a lawsuit seeking police records related to his death, and California Congressman Ro Khanna has "
            "called for a full investigation."
        ),
        keywords=(
            "1. OpenAI\n"
            "2. Artificial Intelligence\n"
            "3. Research Organization\n"
            "4. Whistleblower\n"
            "5. Suchir Balaji\n"
            "6. Lawsuit\n"
            "7. Police Records\n"
            "8. Controversy\n"
            "9. Content Moderation\n"
            "10. Military Use"
        ),
        sentiment="Negative"
    )
    
    try:
        evaluator = URLProcessingEvaluator(llm)
        evaluation = evaluator.evaluate(sample_result)
        evaluator.print_report(evaluation)
        return evaluation
    except Exception as e:
        logger.exception("Error testing evaluator")
        return None

def test_full_pipeline():
    """Test the complete pipeline: process URL then evaluate"""
    print("\n" + "="*60)
    print("TESTING FULL PIPELINE")
    print("="*60)
    
    llm = setup_llm()
    test_url = "https://en.wikipedia.org/wiki/OpenAI"
    
    try:
        # Step 1: Process URL
        logger.info("Step 1: Processing URL...")
        processor = URLProcessor(llm)
        result = processor.process_url(test_url)
        processor.print_report(result)
        
        # Step 2: Evaluate result
        logger.info("Step 2: Evaluating result...")
        evaluator = URLProcessingEvaluator(llm)
        evaluation = evaluator.evaluate(result)
        evaluator.print_report(evaluation)
        
        return result, evaluation
        
    except Exception as e:
        logger.exception("Error in full pipeline test")
        return None, None

def main():
    """Main testing function"""
    print("URL Processing System - Test & Demo")
    print("="*60)
    # test_processor()
    test_evaluator()

if __name__ == "__main__":
    main()