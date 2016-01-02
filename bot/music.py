import asyncio
import discord
import logging
import yolodb


log = logging.getLogger(__name__)


class MusicPlayer(object):

    def __init__(self, client, avconv=False, opus='opus', loop=None):
        # Load opus shared library, might fail
        discord.opus.load_opus(opus)
        self.use_avconv = avconv
        self.loop = loop or asyncio.get_event_loop()
        self.client = client
        self.ended = asyncio.Event()
        self.player = None
        self.play_future = None
        self.db = yolodb.load('music.db')

    @property
    def whitelist(self):
        return self.db.get('whitelist', [])

    def add_user(self, user_id):
        """
        Add a user to be whitelisted for audio
        """
        wl = self.whitelist
        wl.append(user_id)
        self.db.put('whitelist', wl)

    def remove_user(self, user_id):
        """
        Remove a user from the audio whitelist
        """
        wl = self.whitelist
        wl.remove(user_id)
        self.db.put('whitelist', wl)

    def play_song(self, channel, url):
        if self.player:
            log.warning('Something already playing')
            return

        self.play_future = asyncio.ensure_future(self._play_song(channel, url))

    async def _play_song(self, channel, url):
        if self.player:
            log.warning('Something already playing')
            return

        log.info('Joining voice channel %s', channel)
        voice = await self.client.join_voice_channel(channel)
        self.ended.clear()
        log.info('Playing song from url %s', url)
        ydl_opts = {'logger': log}
        self.player = voice.create_ytdl_player(
            url, use_avconv=self.use_avconv, after=self.stop, options=ydl_opts)
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
        if self.player and self.player.is_playing():
            log.info('Something playing, stopping it')
            self.player.stop()
            log.info('Player stopped')
        self.player = None
        self.ended.set()

    async def close(self):
        if self.player:
            self.player.stop()
        self.ended.set()
        if self.play_future:
            await self.play_future
