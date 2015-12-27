import asyncio
from datetime import timedelta, datetime
import logging
import re
from uuid import uuid4

import yolodb


log = logging.getLogger(__name__)


class Reminder(object):

    def __init__(self, uid, author, message, at_time):
        self.uid = uid
        self.author = author
        self.message = message
        self.at_time = at_time


class ReminderManager(object):

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.db = yolodb.load('reminder.db')
        self._regex = re.compile(r'(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?')

    def new(self, author, strtime, message):
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

        # TODO: This should be improved on yolodb's side
        reminders = self.db.get(author) or {}
        reminders[uid] = {
            'at_time': at_time,
            'message': message,
        }
        self.db.put(author, reminders)

        def remind():
            pass

        return True

    def _start_reminder(self, uid):
        pass

    async def close(self):
        await self.db.close()
