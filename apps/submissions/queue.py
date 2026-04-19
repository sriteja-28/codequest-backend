import pika
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_queue_depth():
    """Check RabbitMQ queue depth with caching"""
    cache_key = 'rabbitmq_queue_depth'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        queue = channel.queue_declare(
            queue=settings.JUDGE_QUEUE_NAME,
            durable=True,
            passive=True
        )
        
        depth = queue.method.message_count
        connection.close()
        
        # Cache for 5 seconds
        cache.set(cache_key, depth, 5)
        return depth
        
    except Exception as e:
        logger.error(f"Failed to check queue: {e}")
        return 0  # Fail open


def can_accept_submission(user):
    """Circuit breaker logic"""
    depth = get_queue_depth()
    is_pro = user.is_pro if user.is_authenticated else False
    
    # Hard limit
    if depth > settings.JUDGE_QUEUE_HARD_LIMIT:
        return False, f"Judge queue overloaded ({depth} jobs). Try again in a few minutes."
    
    # Soft limit - PRO only
    if depth > settings.JUDGE_QUEUE_SOFT_LIMIT and not is_pro:
        return False, "Queue is full. Upgrade to PRO for priority access."
    
    return True, None