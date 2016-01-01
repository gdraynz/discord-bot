# A discord bot

A port of my other bot [gobot](https://github.com/gdraynz/gobot) in python, a language I'm more confortable with.

## Features

* `!go played` shows your total game time
* `!go reminder` reminds you of something in some time
 
## Launch it

All you need is a `conf.json` file on the same level as `bot.py` containing :
```json
{
  "email": "my@email.com",
  "password": "my_password",
  "admin_id": "0123456789",
  "prefix": "!my_prefix"
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

## To do

* Reminder management (list, delete)
* Gametime management (at least delete, + admin tool ?)
