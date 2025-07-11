import os
import logging
from langchain_community.document_loaders.web_base import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.common.models import URLProcessingResult

# Set USER_AGENT to avoid warnings
os.environ["USER_AGENT"] = "ContentFilterAndSummarizer/1.0"

logger = logging.getLogger(__name__)

class URLProcessor:
    """Processes URLs to extract summary, keywords, and sentiment"""
    
    def __init__(self, llm):
        self.llm = llm
        self._setup_prompts()
    
    def _setup_prompts(self):
        """Initialize processing prompts"""
        self.keywords_prompt = PromptTemplate(
            input_variables=["text"],
            template="""Extract 5-10 important keywords from the following summary.           
            Summary: {text}
            Format the keywords as a numbered list like this:
            1. Keyword One
            2. Keyword Two
            3. Keyword Three
            Keywords:"""
        )
        
        self.sentiment_prompt = PromptTemplate(
            input_variables=["text"],
            template="""Analyze the overall tone of the following article summary.          
            Your response should reflect the general sentiment expressed in the summary as a whole — 
            not specific words or isolated events.
            Reply with exactly one word: Positive, Neutral, or Negative.
            Summary: {text}
            Sentiment:"""
        )
        
        self.keywords_chain = self.keywords_prompt | self.llm | StrOutputParser()
        self.sentiment_chain = self.sentiment_prompt | self.llm | StrOutputParser()
    
    def process_url(self, url: str) -> URLProcessingResult:
        """
        Process a URL to extract summary, keywords, and sentiment
        
        Args:
            url: URL to process
            
        Returns:
            URLProcessingResult with extracted information
        """
        logger.info(f"Processing URL: {url}")
        
        try:
            logger.info("Loading content from URL...")
            loader = WebBaseLoader(url)
            docs = loader.load()

            if not docs or not docs[0].page_content.strip():
                raise ValueError("No content found at URL")

            logger.info("Splitting text into chunks...")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, 
                chunk_overlap=100
            )
            docs_chunks = text_splitter.split_documents(docs)

            logger.info("Generating summary...")
            summary_chain = load_summarize_chain(self.llm, chain_type="map_reduce")
            summary_result = summary_chain.invoke({"input_documents": docs_chunks})
            summary = summary_result["output_text"]

            logger.info("Extracting keywords...")
            keywords = self.keywords_chain.invoke({"text": summary})

            logger.info("Performing sentiment analysis...")
            sentiment = self.sentiment_chain.invoke({"text": summary}).strip()

            logger.info(f"Successfully processed URL: {url}")
            return URLProcessingResult(
                url=url,
                summary=summary,
                keywords=keywords,
                sentiment=sentiment
            )
            
        except ValueError as e:
            logger.error(f"Content error for URL {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to process URL {url}: {str(e)}")
            raise
    
    def print_report(self, result: URLProcessingResult):
        """Print processing report for debugging"""
        print(f"\n{'='*60}")
        print(f"URL PROCESSING RESULTS")
        print(f"{'='*60}")
        print(f"URL: {result.url}")
        print(f"\nSummary:\n{result.summary}")
        print(f"\nKeywords:\n{result.keywords}")
        print(f"\nSentiment: {result.sentiment}")
        print(f"{'='*60}")