# A discord bot

A port of my other bot [gobot](https://github.com/gdraynz/gobot) in python, a language I'm more confortable with.

## Features

* `!go played` shows your total game time
* `!go reminder <(w)d(x)h(y)m(z)s> [message]` reminds you of something in the given time
* `!go play Voice channel name https://www.youtube.com/watch?v=dQw4w9WgXcQ` play the youtube audio in the given voice channel
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

## To do

* Reminder management (list, delete)
* Gametime management (at least delete, + admin tool ?)
