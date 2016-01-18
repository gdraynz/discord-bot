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

    def __init__(self, name, handler, admin=False, regexp=r''):
        self.name = name
        self.admin = admin
        self.regexp = re.compile(regexp) if regexp else None
        if not asyncio.iscoroutinefunction(handler):
            log.warning('A command must be a coroutine')
            handler = asyncio.coroutine(handler)
        self.handler = handler
        self.help = handler.__doc__ or ''

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
        "scrap_invites": false,

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

        # Store commands
        self.commands = dict()

        # Websocket handlers
        self.client.event(self.on_member_update)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        self.add_command('stats', self._stats)
        self.add_command('help', self._help)
        self.add_command('info', self._info)
        self.add_command('source', self._source)

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

    def add_command(self, *args, **kwargs):
        cmd = Command(*args, **kwargs)
        self.commands[cmd.name] = cmd
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

        try:
            await self.client.connect()
        except discord.ClientException as exc:
            error = "Something broke, I'm out!\n"
            error += '```%s```' % str(exc)
            await self.client.send_message(
                discord.User(id=self.conf['admin_id']),
                error
            )
            self.stop_signal()

    async def stop(self):
        await self._stop_modules()
        await self.client.logout()

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
        if self.conf['scrap_invites']:
            if message.channel.is_private:
                match = re.match(
                    r'(?:https?\:\/\/)?discord\.gg\/(.+)',
                    message.content)
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
        """print the help message"""
        msg = 'Available commands, all preceded by `%s`:\n' % self.conf['prefix']
        for command in self.commands.values():
            if command.admin:
                continue
            msg += '`%s' % command.name
            msg += (' : %s`\n' % command.help) if command.help else '`\n'

        await self.client.send_message(message.channel, msg)

    async def _info(self, message):
        """print your id"""
        await self.client.send_message(
            message.channel, "Your id: `%s`" % message.author.id)

    async def _source(self, message):
        """show the bot's github link"""
        await self.client.send_message(
            message.channel, 'https://github.com/gdraynz/discord-bot'
        )

    async def _stats(self, message):
        """show the bot's general stats"""
        users = 0
        for s in self.client.servers:
            users += len(s.members)

        msg = 'General informations:\n'
        msg += '`Admin             :` <@%s>\n' % self.conf['admin_id']
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
