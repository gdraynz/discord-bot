import asyncio
from datetime import datetime
import json
import logging

import pickledb


log = logging.getLogger(__name__)


class TimeCounter(object):

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.db = None
        self.playing = dict()

        self.request_save = False
        self._save_future = asyncio.ensure_future(self._schedule_save())
        asyncio.ensure_future(self._load_db())

    async def _load_db(self):
        self.db = await self._async_load('game.db')

    async def _async_load(self, db):
        return (await self.loop.run_in_executor(None, pickledb.load, db, False))

    async def _async_dump(self):
        return (await self.loop.run_in_executor(None, self.db.dump))

    async def _schedule_save(self):
        self.request_save = False

        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            log.warning('save schedule cancelled')
            await self._async_dump()
            return

        if self.request_save:
            await self._async_dump()

        self._save_future = asyncio.ensure_future(self._schedule_save())

    def get(self, user_id):
        return json.loads(self.db.get(user_id) or "{}")

    def set(self, user_id, game, time):
        played = self.get(user_id)
        played[game] = played.get(game, 0) + time
        self.db.set(user_id, json.dumps(played))

    async def _count_task(self, user_id, game_name):
        start = datetime.utcnow()

        log.info('Waiting for %s on %s', user_id, game_name)
        await self.playing[user_id]['event'].wait()
        log.info('%s done playing %s', user_id, game_name)

        del self.playing[user_id]
        # Total played
        total = (datetime.utcnow() - start).seconds
        # Add new game time
        self.set(user_id, game_name, total)
        self.request_save = True

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
        if self._save_future:
            self._save_future.cancel()
            await self._save_future
        if self.playing:
            tasks = [p['task'] for p in self.playing.values()]
            for p in self.playing.values():
                p['event'].set()
            await asyncio.wait(tasks, timeout=2)
