#!/usr/bin/env python
import asyncio
from datetime import datetime
import discord
import json
import logging
import logging.config
from signal import SIGINT, SIGTERM

from gametime import TimeCounter
from log import LOGGING_CONF
# from reminder import ReminderManager


log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


def get_time_string(seconds):
    hours = seconds / 3600
    minutes = (seconds / 60) % 60
    seconds = seconds % 60
    return '%0.2d:%02d:%02d' % (hours, minutes, seconds)


class Bot(object):

    def __init__(self):
        self.client = discord.Client(loop=loop)
        self.counter = TimeCounter(loop=loop)
        # self.reminder = ReminderManager(loop=loop)

        self.client.event(self.on_member_update)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        self._start_time = datetime.now()
        self._commands = 0

    async def start(self):
        with open('conf.json', 'r') as f:
            creds = json.loads(f.read())
        await self.client.login(creds['email'], creds['password'])
        await self.client.connect()

    async def stop(self):
        await self.client.close()
        await self.counter.close()
        # await self.reminder.close()

    def stop_signal(self):
        log.info('Closing')
        f = asyncio.ensure_future(self.stop())

        def end(res):
            log.info('Ending loop')
            loop.call_soon_threadsafe(loop.stop)

        f.add_done_callback(end)

    async def on_member_update(self, old, new):
        if new.id in self.counter.playing and not new.game:
            self.counter.done_counting(new.id)
        elif new.id not in self.counter.playing and new.game:
            self.counter.start_counting(new.id, new.game.name)

    async def on_ready(self):
        for server in self.client.servers:
            for member in server.members:
                if member.game:
                    self.counter.start_counting(member.id, member.game.name)
        log.info('everything ready')

    async def on_message(self, message):
        if not message.content.startswith('!go'):
            return

        data = message.content.split(' ')
        if len(data) <= 1:
            return

        cmd = 'command_' + data[1]
        if hasattr(self, cmd):
            self._commands += 1
            await getattr(self, cmd)(message)

    async def command_help(self, message):
        await self.client.send_message(
            message.channel,
            "Available commands, all preceded by `!go`:\n"
            "`help     : show this help message`\n"
            "`stats    : show the bot's statistics`\n"
            "`source   : show the bot's source code (github)`\n"
            "`played   : show your game time`\n"
            # "`reminder : remind you of something in <(w)d(x)h(y)m(z)s>`"
        )

    async def command_played(self, message):
        msg = ''
        played = self.counter.get(message.author.id)

        if played:
            msg += "As far as I'm aware, you played:\n"
            for game, time in played.items():
                msg += '`%s : %s`\n' % (game, get_time_string(time))
        else:
            msg = "I don't remember you playing anything :("

        await self.client.send_message(message.channel, msg)

    # async def command_reminder(self, message):
    #     params = message.content.split(' ')
    #     if len(params) <= 2:
    #         return

    #     time = params[2]
    #     msg = params[3:] if len(params) >= 4 else 'ping!'

    #     self.reminder.new(message.author.id, time, msg)

    async def command_source(self, message):
        await self.client.send_message(
            message.channel, 'https://github.com/gdraynz/discord-bot'
        )

    async def command_stats(self, message):
        msg = 'General statistics:\n'
        msg += '`Uptime            : %s`\n' % get_time_string((datetime.now() - self._start_time).total_seconds())
        msg += '`Commands answered : %d`\n' % self._commands
        msg += '`Users playing     : %d`\n' % len(self.counter.playing)
        await self.client.send_message(message.channel, msg)


def main():
    bot = Bot()

    loop.add_signal_handler(SIGINT, bot.stop_signal)
    loop.add_signal_handler(SIGTERM, bot.stop_signal)

    asyncio.ensure_future(bot.start())
    loop.run_forever()

    loop.close()


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-l', '--logfile', action='store_true', help='Log file')

    args = parser.parse_args()

    if args.logfile:
        LOGGING_CONF['root']['handlers'] = ['logfile']

    logging.config.dictConfig(LOGGING_CONF)

    main()
