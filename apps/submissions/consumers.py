import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

# Application close codes (4000-4999): the frontend stops reconnecting on these.
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


class SubmissionStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket: ws/submissions/{submission_id}/
    Lets the submitting user (or an admin) watch one submission's status.
    The judge callback broadcasts updates to the group; on connect the current
    status is pushed immediately so a verdict that arrived before the socket
    opened is not missed.
    """

    group_name = None

    async def connect(self):
        self.submission_id = str(self.scope["url_route"]["kwargs"]["submission_id"])
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            await self.accept()
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return

        snapshot = await self._snapshot_for(user)
        if snapshot is None:
            await self.accept()
            await self.close(code=CLOSE_FORBIDDEN)
            return

        self.group_name = f"submission_{self.submission_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(json.dumps({"type": "connected", "submission_id": self.submission_id}))
        await self.send(json.dumps({"type": "status_update", **snapshot}))

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _snapshot_for(self, user):
        from .models import Submission
        from .services import submission_snapshot

        qs = Submission.objects.filter(id=self.submission_id)
        if not getattr(user, "is_admin", False):
            qs = qs.filter(user_id=user.pk)
        submission = qs.first()
        return submission_snapshot(submission) if submission else None

    # Receive from group (sent by services.broadcast_submission)
    async def submission_update(self, event):
        await self.send(json.dumps({
            "type": "status_update",
            "submission_id": event["submission_id"],
            "status": event["status"],
            "runtime_ms": event.get("runtime_ms"),
            "memory_kb": event.get("memory_kb"),
        }))
