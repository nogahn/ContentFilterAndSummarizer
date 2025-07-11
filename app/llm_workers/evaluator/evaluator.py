import logging
import re
import json
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from app.common.models import URLProcessingResult, EvaluationOutput, EvaluationScores

logger = logging.getLogger(__name__)

class URLProcessingEvaluator:
    """Evaluates URL processing results for internal consistency"""
    
    def __init__(self, llm):
        self.llm = llm
        self._setup_prompts()
    
    def _setup_prompts(self):
        """Initialize evaluation prompts with Pydantic parsers"""
        
        self.parser = PydanticOutputParser(pydantic_object=EvaluationOutput)
        
        self.summary_prompt = PromptTemplate(
            input_variables=["summary"],
            template="""Rate this summary quality (1-10) and provide explanation.
            Summary: {summary}
            
            Evaluate based on:
            - Clarity: Is the summary easy to understand?
            - Coherence: Does it flow logically?
            - Completeness: Does it cover the main points?
            - Conciseness: Is it appropriately brief without being too short?
            
            Score Guidelines:
            - 9-10: Excellent - Clear, complete, well-structured
            - 7-8: Good - Minor issues with clarity or completeness
            - 5-6: Fair - Some important information missing or unclear
            - 3-4: Poor - Significant clarity or completeness issues
            - 1-2: Very poor - Confusing, incomplete, or incoherent
            IMPORTANT: Return only ONE JSON object with a single overall score.
            {format_instructions}""",
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
            )
        
        self.keywords_prompt = PromptTemplate(
            input_variables=["summary", "keywords"],
            template="""Rate how well these keywords match and represent the summary content (1-10).
            Summary: {summary}
            Keywords: {keywords}
            
            Evaluate based on:
            - Relevance: Are the keywords directly related to the summary content?
            - Coverage: Do the keywords cover the main topics in the summary?
            - Accuracy: Are the keywords correctly extracted from the content?
            - Completeness: Are important topics from the summary represented in keywords?
            
            Score Guidelines:
            - 9-10: Excellent - Keywords perfectly match and cover summary content
            - 7-8: Good - Most keywords relevant, minor gaps or irrelevant terms
            - 5-6: Fair - Some keywords relevant, but missing key topics or some irrelevant terms
            - 3-4: Poor - Many keywords irrelevant or missing important topics
            - 1-2: Very poor - Keywords mostly irrelevant or completely missing key topics
            IMPORTANT: Return only ONE JSON object with a single overall score
            {format_instructions}""",
                        partial_variables={"format_instructions": self.parser.get_format_instructions()}
            )
        
        self.sentiment_prompt = PromptTemplate(
            input_variables=["summary", "sentiment"],
            template="""You are evaluating if the predicted sentiment matches the ACTUAL WRITING TONE of the summary.
            Summary: {summary}
            Predicted Sentiment: {sentiment}

            STEP 1: IDENTIFY THE ACTUAL WRITING TONE
            Read the summary and categorize the tone as:
            - NEUTRAL: Factual, objective, informative, no emotional language
            - NEGATIVE: Critical, condemning, pessimistic, emotional criticism
            - POSITIVE: Enthusiastic, appreciative, celebratory, optimistic praise

            STEP 2: COMPARE TO PREDICTED SENTIMENT
            The predicted sentiment is: {sentiment}

            STEP 3: APPLY STRICT SCORING RULES
            - Predicted "Negative" + Actual NEUTRAL tone = 2/10 (mismatch)
            - Predicted "Positive" + Actual NEUTRAL tone = 2/10 (mismatch)  
            - Predicted "Neutral" + Actual NEUTRAL tone = 9/10 (perfect match)
            - Predicted "Negative" + Actual NEGATIVE tone = 9/10 (perfect match)
            - Predicted "Positive" + Actual POSITIVE tone = 9/10 (perfect match)
            - Any other combination = 1-3/10 (mismatch)

            CRITICAL: You MUST follow these scoring rules exactly. Do not give medium scores (4-7) unless there's partial alignment.

            EXAMPLE ANALYSIS:
            If summary is written neutrally (factual, objective) but predicted sentiment is "Negative":
            - Actual tone: NEUTRAL (factual reporting)
            - Predicted: Negative
            - Match: NO - this is a mismatch
            - Score: 2/10 (following the rule above)

            Your response format:
            {{
            "score": <number 1-10>,
            "explanation": "Actual tone: [NEUTRAL/NEGATIVE/POSITIVE]. Predicted sentiment: {sentiment}. Match: [YES/NO]. Score: [X]/10 because [reason following the rules]."
            }}

            IMPORTANT: Follow the scoring rules exactly. No exceptions.

            {format_instructions}""",
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.summary_chain = self.summary_prompt | self.llm | StrOutputParser()
        self.keywords_chain = self.keywords_prompt | self.llm | StrOutputParser()
        self.sentiment_chain = self.sentiment_prompt | self.llm | StrOutputParser()
    
    def _safe_parse_evaluation(self, response: str) -> EvaluationOutput:
        """Safely parse evaluation response with fallback"""
        logger.info(f"Raw response: {response}")    
        try:
            return self.parser.parse(response)
        except Exception as e:
            logger.warning(f"Pydantic parsing failed: {e}")          
            try:
                json_match = re.search(r'\{[^{}]*"score"[^{}]*"explanation"[^{}]*\}', response, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'\{.*?"score".*?\}', response, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    logger.info(f"Extracted JSON: {json_str}")
                    data = json.loads(json_str)
                    return EvaluationOutput(
                        score=data.get('score', 5),
                        explanation=data.get('explanation', f"Raw response: {response}")
                    )
            except Exception as json_error:
                logger.warning(f"JSON parsing failed: {json_error}")
            
            if response.strip().isdigit():
                score = int(response.strip())
                if 1 <= score <= 10:
                    return EvaluationOutput(
                        score=score,
                        explanation=f"Score only provided: {score}/10 (no explanation given)"
                    )
            
            score_patterns = [
                r'(?:score|rate).*?(\d+)',
                r'(\d+)\s*(?:out of|/)\s*10',
                r'(\d+)\s*(?:points?|pts?)',
            ]
            
            score = 5
            for pattern in score_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    potential_score = int(match.group(1))
                    if 1 <= potential_score <= 10:
                        score = potential_score
                        break
            
            return EvaluationOutput(
                score=score,
                explanation=f"Parsing failed. Raw response: {response.strip()}"
            )
    
    def evaluate(self, result: URLProcessingResult) -> EvaluationScores:
        """
        Evaluate processing result
        
        Args:
            result: URLProcessingResult object
            
        Returns:
            EvaluationScores with scores and overall rating
        """
        logger.info(f"Evaluating URL: {result.url}")
        
        try:
            logger.info("Starting sentiment evaluation...")
            sentiment_response = self.sentiment_chain.invoke({
                "summary": result.summary,
                "sentiment": result.sentiment
            })
            
            logger.info("Starting summary evaluation...")
            summary_response = self.summary_chain.invoke({"summary": result.summary})
            
            logger.info("Starting keywords evaluation...")
            keywords_response = self.keywords_chain.invoke({
                "summary": result.summary, 
                "keywords": result.keywords
            })
            
            summary_eval = self._safe_parse_evaluation(summary_response)
            keywords_eval = self._safe_parse_evaluation(keywords_response)
            sentiment_eval = self._safe_parse_evaluation(sentiment_response)
            
            overall_score = round((summary_eval.score + keywords_eval.score + sentiment_eval.score) / 3, 1)
            
            return EvaluationScores(
                url=result.url,
                summary_quality=summary_eval.score,
                summary_explanation=summary_eval.explanation,
                keywords_relevance=keywords_eval.score,
                keywords_explanation=keywords_eval.explanation,
                sentiment_alignment=sentiment_eval.score,
                sentiment_explanation=sentiment_eval.explanation,
                overall_score=overall_score,
                status="success"
            )
            
        except Exception as e:
            logger.error(f"Evaluation failed: {str(e)}")
            return EvaluationScores(
                url=result.url,
                summary_quality=1,
                summary_explanation="Error occurred during evaluation",
                keywords_relevance=1,
                keywords_explanation="Error occurred during evaluation",
                sentiment_alignment=1,
                sentiment_explanation="Error occurred during evaluation",
                overall_score=1.0,
                status="error",
                error=str(e)
            )
    
    def print_report(self, evaluation: EvaluationScores):
        """Print evaluation report"""
        print(f"\n{'='*60}")
        print(f"EVALUATION REPORT")
        print(f"{'='*60}")
        print(f"URL: {evaluation.url}")
        print(f"Status: {evaluation.status}")
        
        if evaluation.status == 'success':
            print(f"\nSummary Quality: {evaluation.summary_quality}/10")
            print(f"Explanation: {evaluation.summary_explanation}")
            
            print(f"\nKeywords Relevance: {evaluation.keywords_relevance}/10")
            print(f"Explanation: {evaluation.keywords_explanation}")
            
            print(f"\nSentiment Alignment: {evaluation.sentiment_alignment}/10")
            print(f"Explanation: {evaluation.sentiment_explanation}")
            
            print(f"\nOverall Score: {evaluation.overall_score}/10")
            
            score = evaluation.overall_score
            rating = "Excellent" if score >= 8 else "Good" if score >= 6 else "Fair" if score >= 4 else "Poor"
            print(f"Rating: {rating}")
        else:
            print(f"Error: {evaluation.error}")
        
        print(f"{'='*60}")
