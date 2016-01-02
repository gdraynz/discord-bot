LOGGING_CONF = {
    "version": 1,
    "formatters": {
        "long": {
            "format": "%(asctime)-24s %(levelname)-8s [%(name)s] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "long",
            "stream": "ext://sys.stdout"
        },
        "logfile": {
            "class": "logging.FileHandler",
            "formatter": "long",
            "filename": "bot.log"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    },
    "loggers": {
        "asyncio": {
            "level": "WARNING"
        },
        "aiohttp.web": {
            "level": "WARNING"
        },
        "discord.voice_client": {
            "level": "WARNING"
        }
    },
    "disable_existing_loggers": False
}
