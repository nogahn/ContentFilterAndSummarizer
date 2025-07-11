from typing import Optional
from pydantic import BaseModel, Field

class URLProcessingResult(BaseModel):
    """Input model for URL processing and evaluation"""
    url: str = Field(description="The URL that was processed")
    summary: str = Field(description="Generated summary of the URL content")
    keywords: str = Field(description="Extracted keywords from the content")
    sentiment: str = Field(description="Sentiment analysis result")
    overall_score: Optional[float] = Field(default=None, description="Overall evaluation score (1-10)")
    content: Optional[str] = Field(default=None, description="Full article content") # only added to user request

class EvaluationOutput(BaseModel):
    """Generic evaluation output for all evaluation types"""
    score: int = Field(ge=1, le=10, description="Evaluation score (1-10)")
    explanation: str = Field(description="Detailed explanation of the score")

class EvaluationScores(BaseModel):
    """Output model for evaluation results"""
    url: str = Field(description="URL that was evaluated")
    summary_quality: int = Field(ge=1, le=10, description="Summary quality score (1-10)")
    summary_explanation: str = Field(description="Summary quality explanation")
    keywords_relevance: int = Field(ge=1, le=10, description="Keywords relevance score (1-10)")
    keywords_explanation: str = Field(description="Keywords relevance explanation")
    sentiment_alignment: int = Field(ge=1, le=10, description="Sentiment alignment score (1-10)")
    sentiment_explanation: str = Field(description="Sentiment alignment explanation")
    overall_score: float = Field(ge=1.0, le=10.0, description="Overall average score")
    status: str = Field(default="success", description="Evaluation status")
    error: str = Field(default="", description="Error message if any")