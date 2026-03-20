import json
from channels.generic.websocket import AsyncWebsocketConsumer


class LeaderboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket: ws/contests/{contest_slug}/leaderboard/
    Client connects to watch the live leaderboard of a contest.
    Receives broadcasts from the ContestLeaderboardView when rankings update.
    """

    async def connect(self):
        self.contest_slug = self.scope["url_route"]["kwargs"]["contest_slug"]
        self.group_name = f"leaderboard_{self.contest_slug}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(json.dumps({
            "type": "connected",
            "contest_slug": self.contest_slug,
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive from group (sent by AdminContestParticipantView / _broadcast_leaderboard)
    async def leaderboard_update(self, event):
        """Send updated leaderboard entries to all connected clients."""
        await self.send(json.dumps({
            "type": "leaderboard_update",
            "entries": event.get("entries", []),
        }))
