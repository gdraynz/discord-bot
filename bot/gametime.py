import asyncio
from datetime import datetime
import logging
import yolodb

from utils import get_time_string


log = logging.getLogger(__name__)


class TimeCounter(object):

    def __init__(self, bot, loop=None):
        self.bot = bot
        self.loop = loop or asyncio.get_event_loop()
        self.db = None
        self.playing = dict()

    async def start(self):
        self.db = await yolodb.load('gametime.db', loop=self.loop)
        if not self.db.get('start_time'):
            self.db['start_time'] = int(datetime.now().timestamp())

        self.bot.add_command('played', self._played_command)
        self.bot.add_command(
            'add', self._add_command,
            admin=True,
            regexp=r'^(?P<user_id>\d+) (?P<game>.+) (?P<time>\d+)')

    async def stop(self):
        await self.db.close()
        if self.playing:
            tasks = [p['task'] for p in self.playing.values()]
            for p in self.playing.values():
                p['event'].set()
            await asyncio.wait(tasks, timeout=2)
        self.bot.remove_command('played')
        self.bot.remove_command('add')

    @property
    def starttime(self):
        return int(datetime.now().timestamp()) - self.db.get('start_time')

    async def _played_command(self, message):
        """show your game time"""
        msg = ''
        played = self.get(message.author.id)

        if played:
            msg += "As far as i'm aware, you played:\n"
            for game, time in played.items():
                msg += '`%s : %s`\n' % (game, get_time_string(time))
        else:
            msg = "I don't remember you playing anything :("

        await self.bot.client.send_message(message.channel, msg)

    async def _add_command(self, message, user_id, game, time):
        time = int(time)

        old_time = self.get(user_id).get(game, 0)
        self.put(user_id, game, old_time + time)

        await self.bot.client.send_message(message.channel, "done :)")

    def get(self, user_id):
        return self.db.get(user_id, {})

    def put(self, user_id, game, time):
        played = self.db.get(user_id, {})
        played[game] = played.get(game, 0) + time
        self.db[user_id] = played

    async def _count_task(self, user_id, game_name):
        start = datetime.utcnow()

        log.debug('Waiting for %s on %s', user_id, game_name)
        await self.playing[user_id]['event'].wait()
        log.debug('%s done playing %s', user_id, game_name)

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
        # else do not take that into account. One game per user.

    def done_counting(self, user_id):
        if user_id in self.playing:
            self.playing[user_id]['event'].set()
