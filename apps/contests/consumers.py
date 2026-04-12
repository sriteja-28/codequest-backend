import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ContestParticipant
from .serializers import LeaderboardEntrySerializer


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

        # Send current leaderboard immediately on connect
        await self.send(
            json.dumps(
                {
                    "type": "connected",
                    "contest_slug": self.contest_slug,
                }
            )
        )

        # Push current snapshot so client doesn't wait for next update
        entries = await database_sync_to_async(self._get_leaderboard)()
        await self.send(
            json.dumps(
                {
                    "type": "leaderboard_update",
                    "entries": entries,
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive from group (sent by AdminContestParticipantView / _broadcast_leaderboard)
    async def leaderboard_update(self, event):
        """Send updated leaderboard entries to all connected clients."""
        await self.send(
            json.dumps(
                {
                    "type": "leaderboard_update",
                    "entries": event.get("entries", []),
                }
            )
        )

    def _get_leaderboard(self):
        participants = (
            ContestParticipant.objects.filter(
                contest__slug=self.contest_slug,
                is_disqualified=False,
            )
            .select_related("user")
            .order_by("rank", "-final_score")[:50]
        )
        return list(LeaderboardEntrySerializer(participants, many=True).data)
