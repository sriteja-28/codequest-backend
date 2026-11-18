"""
RabbitMQ publisher — used by the Django API to enqueue submission jobs.
The judge worker (judge/worker.py) consumes these jobs.

Message contract (JSON, persistent, durable queue JUDGE_QUEUE_NAME):
    {"submission_id": "<uuid>", "problem_id": <int>, "language": "python|cpp|java|javascript",
     "code": "<source>", "run_sample": <bool>}
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
    # Fail fast instead of hanging the HTTP request when the broker is down or
    # blocking publishers (memory/disk alarm). The caller marks the submission
    # INTERNAL_ERROR and answers 503.
    params.socket_timeout = 5
    params.blocked_connection_timeout = 10
    params.connection_attempts = 1
    return pika.BlockingConnection(params)


def publish_submission_job(submission_id: str, problem_id: int, language: str, code: str, run_sample: bool = False) -> bool:
    """
    Enqueue a submission for the judge worker.
    Uses a durable queue + persistent messages so jobs survive RabbitMQ restarts.
    Returns True when the broker accepted the message.
    """
    payload = {
        "submission_id": str(submission_id),
        "problem_id": problem_id,
        "language": language,
        "code": code,
        "run_sample": run_sample,
    }

    try:
        connection = _get_connection()
        try:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent,
                    content_type="application/json",
                    message_id=str(submission_id),
                ),
            )
        finally:
            connection.close()
        logger.info("Enqueued submission %s (lang=%s, sample=%s)", submission_id, language, run_sample)
        return True

    except Exception as exc:
        logger.error("Failed to enqueue submission %s: %s", submission_id, exc)
        return False
