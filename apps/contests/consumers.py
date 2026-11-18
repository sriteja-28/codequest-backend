import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.core.features import feature_enabled_for

from .access import visible_contest
from .finalize import maybe_finalize
from .views import leaderboard_group, leaderboard_snapshot


class LeaderboardConsumer(AsyncWebsocketConsumer):
    """Public contest standings; private contests are visible only to admins.

    REST and sockets share the same access check. Application close 4404 also
    stops the client reconnecting to an unavailable contest.
    """

    group_name = None

    async def connect(self):
        self.contest_slug = self.scope["url_route"]["kwargs"]["contest_slug"]
        if not await self._visible():
            await self.accept()
            await self.close(code=4404)
            return

        self.group_name = leaderboard_group(self.contest_slug)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(json.dumps({"type": "connected", "contest_slug": self.contest_slug}))
        snapshot = await self._snapshot()
        if snapshot is None:
            await self.close(code=4404)
        else:
            await self.send(json.dumps(snapshot))

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def leaderboard_update(self, event):
        # Visibility can change while a socket is connected.
        if not await self._visible():
            await self.close(code=4404)
            return
        await self.send(json.dumps(event))

    @database_sync_to_async
    def _visible(self):
        user = self.scope.get("user")
        if not feature_enabled_for(user, "contests"):
            return False
        return visible_contest(user=user, slug=self.contest_slug) is not None

    @database_sync_to_async
    def _snapshot(self):
        user = self.scope.get("user")
        contest = visible_contest(user=user, slug=self.contest_slug) if feature_enabled_for(user, "contests") else None
        if contest is None:
            return None
        maybe_finalize(contest)
        return leaderboard_snapshot(contest)
