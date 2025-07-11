import redis
from app.common.config import REDIS_HOST, REDIS_PORT

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_redis_key(url: str) -> str:
    # Generate Redis key for storing URL result
    return f"url_result:{url}"
