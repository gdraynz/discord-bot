import asyncio
from datetime import timedelta, datetime
from discord.user import User
import logging
from uuid import uuid4
import yolodb

from utils import get_time_string


log = logging.getLogger(__name__)


class Reminder(object):

    def __init__(self, uid, author_id, message, at_time):
        self.uid = uid
        self.author = User(id=author_id)
        self.message = message
        self.at_time = at_time

    @classmethod
    def from_dict(cls, **data):
        return cls(**data)

    def to_dict(self):
        return {
            'uid': self.uid,
            'author_id': self.author.id,
            'message': self.message,
            'at_time': self.at_time
        }


"""
<user_id>
    <reminder_id>
        <reminder_id>
        <author_id>
        <message>
        <at_time>
"""


class ReminderManager(object):

    def __init__(self, bot, loop=None):
        self.bot = bot
        self.loop = loop or asyncio.get_event_loop()
        self.db = None
        self.running_tasks = dict()

    async def start(self):
        self.db = await yolodb.load('reminder.db', loop=self.loop)
        for user in self.db.all.values():
            for reminder in user.values():
                self._prepare_reminder(Reminder.from_dict(**reminder))

        self.bot.add_command(
            'reminder', self._command,
            regexp=r'^(?:(?P<days>\d+)d)?'
                   r'(?:(?P<hours>\d+)h)?'
                   r'(?:(?P<minutes>\d+)m)?'
                   r'(?:(?P<seconds>\d+)s)?'
                   r'(?: (?P<remind>.+))?')
        self.bot.add_command('reminder_list', self._command_list)
        self.bot.add_command(
            'reminder_delete', self._command_delete,
            regexp=r'^(?P<uid>\w{8})$')

    async def stop(self):
        await self.db.close()
        self.bot.remove_command('reminder')

    async def _command(self, message, remind=None,
                       days=None, hours=None, minutes=None, seconds=None):
        """remind you of something in <(w)d(x)h(y)m(z)s>"""
        kwargs = {}
        if days:
            kwargs['days'] = int(days)
        if hours:
            kwargs['hours'] = int(hours)
        if minutes:
            kwargs['minutes'] = int(minutes)
        if seconds:
            kwargs['seconds'] = int(seconds)

        log.debug('reminder kwargs: %s', kwargs)

        # Convert it to a unix timestamp
        at_time = int((datetime.now() + timedelta(**kwargs)).timestamp())
        msg = remind or 'ping!'

        self.new(message.author.id, at_time, msg)
        response = 'Aight! I will ping you :)'

        await self.bot.client.send_message(message.channel, response)

    async def _command_list(self, message):
        """List your reminders"""
        reminders = self.get_reminders(message.author.id)
        log.info(reminders)
        if not reminders:
            msg = "I don't have any reminder for you!"
        else:
            msg = 'Here are your current reminders:\n'
            for reminder in reminders.values():
                in_time = reminder['at_time'] - int(datetime.now().timestamp())
                msg += '`%s` "%s" in %s\n' % (reminder['uid'], reminder['message'], get_time_string(in_time))

        await self.bot.client.send_message(message.author, msg)

    async def _command_delete(self, message, uid):
        """Remove the given reminder by uid"""
        if uid in self.running_tasks:
            self._pop_reminder(message.author.id, uid)
            msg = 'Reminder deleted :)'
        else:
            msg = "Don't know about this one, check your list again"
        await self.bot.client.send_message(message.channel, msg)

    def new(self, author_id, at_time, message):
        """
        Take the raw (0d0h0m0s) message and convert it into a reminder
        """
        uid = str(uuid4())[:8]
        reminders = self.db.get(author_id, {})
        new = Reminder(uid, author_id, message, at_time)
        reminders[uid] = new.to_dict()
        self.db[author_id] = reminders
        self._prepare_reminder(new)
        return True

    def get_reminders(self, user_id):
        return self.db.get(user_id, {})

    def _pop_reminder(self, author_id, reminder_id):
        reminders = self.db.get(author_id, {})
        del reminders[reminder_id]
        if not reminders:
            self.db.pop(author_id)
        else:
            self.db[author_id] = reminders
        if reminder_id in self.running_tasks:
            self.running_tasks[reminder_id].cancel()
            del self.running_tasks[reminder_id]

    def _prepare_reminder(self, reminder):
        delay = (reminder.at_time - datetime.now().timestamp())
        log.info('Reminder will be sent in %d seconds', delay)

        def send():
            asyncio.ensure_future(self.bot.client.send_message(
                reminder.author, '`Reminder` ' + reminder.message
            ), loop=self.loop)
            self._pop_reminder(reminder.author.id, reminder.uid)

        self.running_tasks[reminder.uid] = self.loop.call_later(delay, send)
