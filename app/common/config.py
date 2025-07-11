import os
from dotenv import load_dotenv
import pika
import redis

# Load environment variables from .env file
load_dotenv()

# -------------------------------
# RabbitMQ Configuration
# -------------------------------

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST") or "127.0.0.1"
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT") or 5672)
RABBITMQ_USER = os.getenv("RABBITMQ_USER") or "guest"
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD") or "guest"
RABBITMQ_AMQP_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

RABBITMQ_CREDENTIALS = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
rabbitmq_parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    credentials=RABBITMQ_CREDENTIALS,
)

# -------------------------------
# Redis Configuration
# -------------------------------

REDIS_HOST = os.getenv("REDIS_HOST") or "localhost"
REDIS_PORT = int(os.getenv("REDIS_PORT") or 6379)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# -------------------------------
# LLM Configuration
# -------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "groq"
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME") or None
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or 0.3)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS") or 512)

def get_required_api_key(env_var: str, provider: str) -> str:
    key = os.getenv(env_var)
    if not key:
        raise ValueError(f"{env_var} is required for provider '{provider}'")
    return key

def get_llm(
    provider: str = LLM_PROVIDER,
    model_name: str = LLM_MODEL_NAME,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS
):
    provider = provider.lower()
    model_name = model_name or {
        "groq": "llama3-8b-8192",
        "openai": "gpt-4o",
        "gemini": "gemini-1.5-pro-latest",
        "claude": "claude-3-haiku-20240307"
    }.get(provider)

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name,
            groq_api_key=get_required_api_key("GROQ_API_KEY", provider),
            temperature=temperature,
            max_tokens=max_tokens
        )

    elif provider == "openai":
        from langchain.chat_models import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=get_required_api_key("OPENAI_API_KEY", provider),
            temperature=temperature,
            max_tokens=max_tokens
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=get_required_api_key("GOOGLE_API_KEY", provider),
            temperature=temperature
        )

    elif provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=get_required_api_key("ANTHROPIC_API_KEY", provider),
            temperature=temperature,
            max_tokens=max_tokens
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

# -------------------------------
# Queue Names
# -------------------------------

QUEUE_URL_TASKS = "url_tasks"
QUEUE_EVALUATION_TASKS = "evaluation_tasks"
QUEUE_STATUS_UPDATES = "status_updates"

# -------------------------------
# Allowed Domains
# -------------------------------

ALLOWED_DOMAINS = {
    "www.bbc.com",
    "edition.cnn.com",
    "www.reuters.com",
    "www.theguardian.com",
    "techcrunch.com",
    "www.nature.com",
}

# -------------------------------
# Consumer and Retry Settings
# -------------------------------

PROCESSOR_PREFETCH_COUNT = int(os.getenv("PROCESSOR_PREFETCH_COUNT") or 1)
EVALUATOR_PREFETCH_COUNT = int(os.getenv("EVALUATOR_PREFETCH_COUNT") or 1)
WEBSOCKET_CONSUMER_PREFETCH_COUNT = int(os.getenv("WEBSOCKET_CONSUMER_PREFETCH_COUNT") or 10)

EVALUATOR_SCORE_THRESHOLD = float(os.getenv("EVALUATOR_SCORE_THRESHOLD") or 7.0)

MAX_RETRIES_URL_TASK = int(os.getenv("MAX_RETRIES_URL_TASK") or 3)
MAX_RETRIES_EVALUATION_TASK = int(os.getenv("MAX_RETRIES_EVALUATION_TASK") or 3)
