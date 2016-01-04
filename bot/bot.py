#!/usr/bin/env python
import asyncio
from datetime import datetime
import discord
import json
import logging
import logging.config
import re
from signal import SIGINT, SIGTERM

from gametime import TimeCounter
from log import LOGGING_CONF
from music import MusicPlayer
from reminder import ReminderManager
from utils import get_time_string


log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


class Command(object):

    """
    regexp must be a regexp object (re.compile(...))
    """

    def __init__(self, name, handler, admin=False, regexp=r''):
        self.name = name
        self.admin = admin
        self.regexp = re.compile(regexp)
        if not asyncio.iscoroutinefunction(handler):
            log.warning('A command must be a coroutine')
            handler = asyncio.coroutine(handler)
        self.handler = handler

    def __str__(self):
        return '<Command {}: admin={}, regexp={}>'.format(
            self.name, self.admin, bool(self.regexp))

    async def call(self, message):
        data = ' '.join(message.content.split(' ')[2:])
        if self.regexp:
            log.info('Regexp required for command %s', self)
            match = self.regexp.match(data)
            if not match:
                log.error('Regexp failed')
                return
            log.debug('kwargs for cmd: %s', match.groupdict())
            log.info('Calling handler with kwargs for command %s', self)
            await self.handler(message, **match.groupdict())
        else:
            log.info('Calling handler for command %s', self)
            await self.handler(message)


class Bot(object):

    """
    Make use of a conf.json file at work directory:
    {
        "email": "my.email@server.com",
        "password": "my_password",
        "admin_id": "id_of_the_bot_admin",
        "prefix": "!go",

        "music": {
            "avconv": false,

            # Optional, defaulted to 'opus'
            "opus": "opus shared library"
        }
    }
    """

    def __init__(self):

        with open('conf.json', 'r') as f:
            self.conf = json.loads(f.read())

        # Main parts of the bot
        self.client = discord.Client(loop=loop)
        self.modules = dict()
        self.invite_regexp = re.compile(r'(?:https?\:\/\/)?discord\.gg\/(.+)')

        # Store commands
        self.commands = dict()

        # Websocket handlers
        self.client.event(self.on_member_update)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        self.add_command('stats', self._stats)
        self.add_command('help', self._help)
        self.add_command('info', self._info)

        # Other commands are added in their own module (calling bot's method)

        self._start_time = datetime.now()
        self._commands = 0

    def __getattribute__(self, name):
        """
        getattr or take it from the modules dict
        """
        try:
            return super().__getattribute__(name)
        except AttributeError as exc:
            try:
                return self.modules[name]
            except KeyError:
                raise exc

    def add_command(self, name, handler, admin=False, regexp=r''):
        cmd = Command(name, handler, admin=admin, regexp=regexp)
        self.commands[name] = cmd
        log.info('Added command %s', cmd)

    def remove_command(self, name):
        try:
            del self.commands[name]
        except KeyError:
            log.error('No such command: %s', name)

    async def _add_module(self, cls, *args, **kwargs):
        module = cls(*args, **kwargs)
        try:
            await module.start()
        except Exception as exc:
            log.error('Module %s could not start properly', cls)
            log.error('dump: %s', exc)
        else:
            self.modules[cls.__name__.lower()] = module
            log.info('Module %s successfully started', cls)

    async def _stop_modules(self):
        """
        Stop all modules, with a timeout of 2 seconds
        """
        tasks = []
        for module in self.modules.values():
            tasks.append(asyncio.ensure_future(module.stop()))
        done, not_done = await asyncio.wait(tasks, timeout=2)
        if not_done:
            log.error('Stop tasks not done: %s', not_done)
        log.info('Modules stopped')

    async def start(self):
        asyncio.ensure_future(self._add_module(TimeCounter, self, loop=loop))
        asyncio.ensure_future(self._add_module(ReminderManager, self, loop=loop))
        asyncio.ensure_future(self._add_module(
            MusicPlayer, self, **self.conf['music'], loop=loop
        ))
        await self.client.login(self.conf['email'], self.conf['password'])
        await self.client.connect()

    async def stop(self):
        await self._stop_modules()
        await self.client.close()

    def stop_signal(self):
        log.info('Closing')
        f = asyncio.ensure_future(self.stop())

        def end(res):
            log.info('Ending loop')
            loop.call_soon_threadsafe(loop.stop)

        f.add_done_callback(end)

    # Websocket handlers

    async def on_member_update(self, old, new):
        if not self.timecounter:
            log.debug('timecounter not initialized')
            return
        if new.id in self.timecounter.playing and not new.game:
            self.timecounter.done_counting(new.id)
        elif new.id not in self.timecounter.playing and new.game:
            self.timecounter.start_counting(new.id, new.game.name)

    async def on_ready(self):
        for server in self.client.servers:
            for member in server.members:
                if member.game:
                    self.timecounter.start_counting(member.id, member.game.name)
        log.info('everything ready')

    async def on_message(self, message):
        # If invite in private message, join server
        if message.channel.is_private:
            match = self.invite_regexp.match(message.content)
            if match and match.group(1):
                await self.client.accept_invite(match.group(1))
                log.info('Joined server, invite %s', match.group(1))
                await self.client.send_message(
                    message.author, 'Joined it, thanks :)')
                return

        if not message.content.startswith(self.conf['prefix']):
            return

        data = message.content.split(' ')
        if len(data) <= 1:
            log.debug('no command in message')
            return

        cmd = self.commands.get(data[1])

        if not cmd:
            log.debug('%s not a command', data[1])
            return
        elif cmd.admin and message.author.id != self.conf['admin_id']:
            log.warning('cmd %s requires admin', cmd)
            return

        # Go on.
        log.info('Found command %s, calling it', cmd)
        self._commands += 1
        await cmd.call(message)

    # Commands

    async def _help(self, message):
        await self.client.send_message(
            message.channel,
            "Available commands, all preceded by `!go`:\n"
            "`help     : show this help message`\n"
            "`stats    : show the bot's statistics`\n"
            "`source   : show the bot's source code (github)`\n"
            "`played   : show your game time`\n"
            "`reminder : remind you of something in <(w)d(x)h(y)m(z)s>`\n"
            "`play <channel name> <youtube url>`\n"
            "`stop     : Stop the music player`\n"
        )

    async def _info(self, message):
        await self.client.send_message(
            message.channel, "Your id: `%s`" % message.author.id)

    async def _source(self, message):
        await self.client.send_message(
            message.channel, 'https://github.com/gdraynz/discord-bot'
        )

    async def _stats(self, message):
        users = 0
        for s in self.client.servers:
            users += len(s.members)

        msg = 'General statistics:\n'
        msg += '`Uptime            : %s`\n' % get_time_string((datetime.now() - self._start_time).total_seconds())
        msg += '`Users in touch    : %s in %s servers`\n' % (users, len(self.client.servers))
        msg += '`Commands answered : %d`\n' % self._commands
        msg += '`Users playing     : %d`\n' % len(self.timecounter.playing)
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
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')

    args = parser.parse_args()

    if args.logfile:
        LOGGING_CONF['root']['handlers'] = ['logfile']
    if args.debug:
        LOGGING_CONF['root']['level'] = 'DEBUG'

    logging.config.dictConfig(LOGGING_CONF)

    main()
