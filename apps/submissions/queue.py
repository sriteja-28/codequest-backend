import logging

import pika
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = "rabbitmq_queue_depth"


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception as exc:  # cache backend down must not break submissions
        logger.warning("Queue-depth cache read failed: %s", exc)
        return None


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        logger.warning("Queue-depth cache write failed: %s", exc)


def get_queue_depth():
    """Check RabbitMQ queue depth (cached for 5 s). Returns 0 if unknown (fail
    open: the publish step itself reports broker outages as 503)."""
    cached = _cache_get(_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        params.socket_timeout = 3
        params.blocked_connection_timeout = 3
        connection = pika.BlockingConnection(params)
        try:
            channel = connection.channel()
            queue = channel.queue_declare(queue=settings.JUDGE_QUEUE_NAME, durable=True, passive=True)
            depth = queue.method.message_count
        finally:
            connection.close()
    except Exception as e:
        logger.error("Failed to check queue depth: %s", e)
        return 0

    _cache_set(_CACHE_KEY, depth, 5)
    return depth


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
