import asyncio
from datetime import timedelta, datetime
from discord.user import User
import logging
import re
from uuid import uuid4

import yolodb


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

    def __init__(self, client, loop=None):
        self.client = client
        self.loop = loop or asyncio.get_event_loop()
        self.db = yolodb.load('reminder.db')
        self._regex = re.compile(r'(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?')

    async def start(self):
        for user in self.db.all.values():
            for reminder in user.values():
                self._prepare_reminder(Reminder.from_dict(**reminder))

    async def stop(self):
        await self.db.close()

    def new(self, author_id, strtime, message):
        """
        Take the raw (0d0h0m0s) message and convert it into a reminder
        """
        m = self._regex.match(strtime)
        if not m:
            log.warning('Reminder regex did not match')
            return False

        kwargs = {}
        if m.group('days'):
            kwargs['days'] = int(m.group('days'))
        if m.group('hours'):
            kwargs['hours'] = int(m.group('hours'))
        if m.group('minutes'):
            kwargs['minutes'] = int(m.group('minutes'))
        if m.group('seconds'):
            kwargs['seconds'] = int(m.group('seconds'))

        if not kwargs:
            return

        # Get the timedelta
        delay = timedelta(**kwargs)
        # Convert it to a unix timestamp
        at_time = int((datetime.now() + delay).timestamp())
        # Create a uid (because why not)
        uid = str(uuid4())[:8]

        reminders = self.db.get(author_id, {})
        new = Reminder(uid, author_id, message, at_time)
        reminders[uid] = new.to_dict()
        self.db.put(author_id, reminders)
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
            self.db.put(author_id, reminders)

    def _prepare_reminder(self, reminder):
        delay = (reminder.at_time - datetime.now().timestamp())
        log.info('Reminder will be sent in %d seconds', delay)

        def send():
            asyncio.ensure_future(self.client.send_message(
                reminder.author, '`Reminder` ' + reminder.message
            ))
            self._pop_reminder(reminder.author.id, reminder.uid)

        self.loop.call_later(delay, send)
