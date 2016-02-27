import asyncio
import discord
import logging
import yolodb


log = logging.getLogger(__name__)


class MusicPlayer(object):

    def __init__(self, bot, avconv=False, opus='opus', loop=None):
        self.use_avconv = avconv
        self.opus_library = opus
        self.loop = loop or asyncio.get_event_loop()
        self.bot = bot
        self.ended = asyncio.Event()
        self.player = None
        self.play_future = None
        self.db = None

    @property
    def whitelist(self):
        return self.db.get('whitelist', [])

    async def start(self):
        # Load opus shared library, might fail
        discord.opus.load_opus(self.opus_library)

        self.db = await yolodb.load('music.db', loop=self.loop)

        self.bot.add_command(
            'play', self._command_play_song,
            regexp=r'^(?P<channel>.+) '
                   r'(?P<url>https:\/\/www.youtube.com\/watch\?v=.+)')
        self.bot.add_command('stop', self._command_stop_song)
        self.bot.add_command(
            'add_user', self._command_add_user,
            admin=True, regexp=r'^(?P<user_id>\d+)')
        self.bot.add_command(
            'remove_user', self._command_remove_user,
            admin=True, regexp=r'^(?P<user_id>\d+)')

    async def stop(self):
        if self.player:
            self.player.stop()
        self.ended.set()
        if self.play_future:
            await self.play_future
        await self.db.close()

    async def _command_play_song(self, message, url, channel):
        """<voice channel> <youtube url>"""
        if self.player:
            self.stop_player()
            await self.play_future

        check = lambda c: c.name == channel and c.type == discord.ChannelType.voice
        channel = discord.utils.find(check, message.server.channels)
        if channel is None:
            await self.bot.client.send_message(
                message.channel,
                'Does that channel even exist ? :|')
            return

        self.play_song(channel, url)

    async def _command_stop_song(self, message):
        """stop the currently playing song"""
        if message.author.id not in self.whitelist:
            await self.bot.client.send_message(message.channel, "Nah, not you.")
            return

        self.stop_player()

    async def _command_add_user(self, message, user_id):
        self.add_user(user_id)
        await self.bot.client.send_message(message.channel, "Done :)")

    async def _command_remove_user(self, message, user_id):
        self.remove_user(user_id)
        await self.bot.client.send_message(message.channel, "Done :)")

    def add_user(self, user_id):
        """
        Add a user to be whitelisted for audio
        """
        wl = self.whitelist
        wl.append(user_id)
        self.db['whitelist'] = wl

    def remove_user(self, user_id):
        """
        Remove a user from the audio whitelist
        """
        wl = self.whitelist
        wl.remove(user_id)
        self.db['whitelist'] = wl

    def play_song(self, channel, url):
        if self.player:
            log.warning('Something already playing')
            return

        self.play_future = asyncio.ensure_future(
            self._play_song(channel, url), loop=self.loop)

    async def _play_song(self, channel, url):
        if self.player:
            log.warning('Something already playing')
            return

        log.info('Joining voice channel %s', channel)
        voice = await self.bot.client.join_voice_channel(channel)
        self.ended.clear()
        log.info('Playing song from url %s', url)
        ydl_opts = {'logger': log}
        self.player = await voice.create_ytdl_player(
            url, use_avconv=self.use_avconv, after=self.stop_player, options=ydl_opts)
        self.player.start()
        log.info('Waiting for it to end...')
        await self.ended.wait()
        await voice.disconnect()

    def resume_player(self):
        if self.player and not self.player.is_playing():
            log.info('Resuming paused player')
            self.player.resume()

    def pause_player(self):
        if self.player and self.player.is_playing():
            log.info('Pausing player')
            self.player.pause()

    def stop_player(self):
        if self.player and self.player.is_playing():
            log.info('Something playing, stopping it')
            self.player.stop()
            log.info('Player stopped')
        self.player = None
        self.ended.set()
