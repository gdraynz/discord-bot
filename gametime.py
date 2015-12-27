import asyncio
from datetime import datetime
import logging

import yolodb


log = logging.getLogger(__name__)


class TimeCounter(object):

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.db = yolodb.load('gametime.db')
        self.playing = dict()

    def get(self, user_id):
        return self.db.get(user_id)

    def put(self, user_id, game, time):
        played = self.get(user_id) or {}
        played[game] = played.get(game, 0) + time
        self.db.put(user_id, played)

    async def _count_task(self, user_id, game_name):
        start = datetime.utcnow()

        log.info('Waiting for %s on %s', user_id, game_name)
        await self.playing[user_id]['event'].wait()
        log.info('%s done playing %s', user_id, game_name)

        del self.playing[user_id]
        # Total played
        total = (datetime.utcnow() - start).seconds
        # Add new game time
        self.put(user_id, game_name, total)

    def start_counting(self, user_id, game_name):
        if user_id not in self.playing:
            self.playing[user_id] = {
                'event': asyncio.Event(),
                'task': asyncio.ensure_future(self._count_task(user_id, game_name))
            }
        else:
            log.warning('user %s already playing something', user_id)

    def done_counting(self, user_id):
        if user_id in self.playing:
            self.playing[user_id]['event'].set()

    async def close(self):
        await self.db.close()
        if self.playing:
            tasks = [p['task'] for p in self.playing.values()]
            for p in self.playing.values():
                p['event'].set()
            await asyncio.wait(tasks, timeout=2)
