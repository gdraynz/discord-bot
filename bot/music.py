import asyncio
import discord
import logging


log = logging.getLogger(__name__)


class MusicPlayer(object):

    def __init__(self, opus='opus', loop=None):
        # Load opus shared library
        discord.opus.load_opus(opus)
        self.loop = loop or asyncio.get_event_loop()
        self.ended = asyncio.Event()
        self.player = None

    async def play_song(self, voice, url):
        if self.player:
            log.warning('Something already playing')
            return

        self.ended.clear()
        log.info('Playing song from url %s', url)
        self.player = voice.create_ytdl_player(url, after=self.stop)
        self.player.start()
        log.info('Waiting for it to end...')
        await self.ended.wait()
        await voice.disconnect()

    def resume(self):
        if self.player and not self.player.is_playing():
            log.info('Resuming paused player')
            self.player.resume()

    def pause(self):
        if self.player and self.player.is_playing():
            log.info('Pausing player')
            self.player.pause()

    def stop(self):
        if self.player and not self.player.is_playing():
            log.info('Something playing, stopping it')
            self.player.stop()
        self.player = None
        log.info('Player stopped')
        self.ended.set()

    async def close(self):
        if self.player:
            self.player.stop()
        self.ended.set()
