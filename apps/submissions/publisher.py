"""
RabbitMQ publisher — used by the Django API to enqueue submission jobs.
The judge worker (judge/worker.py) consumes these jobs.
"""

import json
import logging
import pika
from django.conf import settings

logger = logging.getLogger(__name__)

QUEUE_NAME = settings.JUDGE_QUEUE_NAME


def _get_connection():
    params = pika.URLParameters(settings.RABBITMQ_URL)
    params.heartbeat = 60
    params.blocked_connection_timeout = 300
    return pika.BlockingConnection(params)


def publish_submission_job(submission_id: str, problem_id: int, language: str, code: str):
    """
    Enqueue a submission for the judge worker.
    Uses a durable queue so jobs survive RabbitMQ restarts.
    """
    payload = {
        "submission_id": str(submission_id),
        "problem_id": problem_id,
        "language": language,
        "code": code,
    }

    try:
        connection = _get_connection()
        channel = connection.channel()

        channel.queue_declare(
            queue=QUEUE_NAME,
            durable=True,  # Survive broker restart
        )

        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,  # Message survives restart
                content_type="application/json",
            ),
        )

        connection.close()
        logger.info(f"Enqueued submission {submission_id} (lang={language})")
        return True

    except Exception as exc:
        logger.error(f"Failed to enqueue submission {submission_id}: {exc}")
        return False