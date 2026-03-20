import json
from channels.generic.websocket import AsyncWebsocketConsumer


class SubmissionStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket: ws/submissions/{submission_id}/
    Client connects to watch a single submission's status in real-time.
    The judge callback view broadcasts updates to this group.
    """

    async def connect(self):
        self.submission_id = self.scope["url_route"]["kwargs"]["submission_id"]
        self.group_name = f"submission_{self.submission_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(json.dumps({"type": "connected", "submission_id": self.submission_id}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive from group (sent by JudgeCallbackView)
    async def submission_update(self, event):
        await self.send(json.dumps({
            "type": "status_update",
            "submission_id": event["submission_id"],
            "status": event["status"],
            "runtime_ms": event.get("runtime_ms"),
            "memory_kb": event.get("memory_kb"),
        }))