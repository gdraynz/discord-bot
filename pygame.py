#!/usr/bin/env python

import asyncio
import discord
import json
import logging
import logging.config
from signal import SIGINT, SIGTERM

from gametime import TimeCounter
from log import LOGGING_CONF


logging.config.dictConfig(LOGGING_CONF)
log = logging.getLogger(__name__)


loop = asyncio.get_event_loop()
client = discord.Client(loop=loop)
counter = TimeCounter(loop=loop)


def get_time_string(seconds):
    hours = seconds / 3600
    minutes = (seconds / 60) % 60
    seconds = seconds % 60
    return '%0.2d:%02d:%02d' % (hours, minutes, seconds)


@client.event
async def on_ready():
    for server in client.servers:
        for member in server.members:
            if member.game:
                counter.start_counting(member.id, member.game.name)

    log.info('everything ready')


@client.event
async def on_message(message):
    if not message.content.startswith('!go'):
        return

    data = message.content.split(' ')
    if len(data) <= 1:
        return

    if len(data) >= 2:
        cmd = data[1]

    if cmd == 'played':
        msg = ''
        played = counter.get(message.author.id)

        if played:
            msg += "As far as I'm aware, you played:\n"
            for game, time in played.items():
                msg += '`%s : %s`\n' % (game, get_time_string(time))
        else:
            msg = "I don't remember you playing anything :("

        await client.send_message(message.channel, msg)


@client.event
async def on_member_update(old, new):
    if new.id in counter.playing and not new.game:
        counter.done_counting(new.id)
    elif new.id not in counter.playing and new.game:
        counter.start_counting(new.id, new.game.name)


async def start():
    with open('conf.json', 'r') as f:
        creds = json.loads(f.read())
    await client.login(creds['email'], creds['password'])
    await client.connect()


async def stop():
    await client.close()
    await counter.close()


def loop_stop():
    log.info('Closing')
    f = asyncio.ensure_future(stop())

    def end(res):
        log.info('Ending loop')
        loop.call_soon_threadsafe(loop.stop)

    f.add_done_callback(end)


def main():
    loop.add_signal_handler(SIGINT, loop_stop)
    loop.add_signal_handler(SIGTERM, loop_stop)

    asyncio.ensure_future(start())
    loop.run_forever()

    loop.close()


if __name__ == '__main__':
    main()
