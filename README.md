# A discord bot

A port of my other bot [gobot](https://github.com/gdraynz/gobot) in python, a language I'm more confortable with.

## Features

* `!go played` shows your total game time
* `!go reminder <(w)d(x)h(y)m(z)s> [message]` reminds you of something in the given time
* `!go play Voice channel name https://www.youtube.com/watch?v=3gxNW2Ulpwk` play the youtube audio in the given voice channel
* `!go stop` stop the audio

## Launch it

All you need is a `conf.json` file on the same level as `bot.py` containing :
```json
{
    "email": "my@email.com",
    "password": "my_password",
    "admin_id": "0123456789",
    "prefix": "my_prefix",
    "music": {
        "avconv": false,
        "opus": "path_to_opus_lib"
    }
}
```
Then launch the bot :
```bash
python3.5 bot.py
```
or launch it in background :
```bash
python3.5 bot.py -l bot.log & # Start the bot and logs into 'bot.log'
echo $! > bot.pid # Store its pid in 'bot.pid' file
...
kill `cat bot.pid` # Kill the bot
```
The bot will respond to every message which begin with `my_prefix` (try `my_prefix help`)

## Commands

To add commands, just follow the commands already in place.

```python
# Example to tell the bot to say something

# Adding admin=True will only allow the command to the admin user
self.add_command('say', self._command_say, regexp=r'(?P<to_say>\w+)')

async def _command_say(self, message, to_say):
    await self.client.send_message(message.channel, to_say)
```
And that's it. just write `!my_prefix say Hey there!` in a channel.

## To do

* Reminder management (list, delete)
* Gametime management (at least delete, + admin tool ?)
