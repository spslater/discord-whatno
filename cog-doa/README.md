# Discord Reread
Discord Reread will upload comics from a week period each time it's run.

## Instalation
```
pip install -r requirements.txt
```

Requires:
- `discord.py`: 1.7.3
- `python-dotenv`: 0.18.0


## Running
The bot only needs permission to Send Messages to a server to operate.

Command line args will override values in the `.env` file.

```shell
usage: discordcli [-h [HELP ...]]
               [--logfile LOGFILE] [-q] [--level LEVEL]
               [-e ENV] [-t TOKEN] [-g GUILD] [-c CHANNEL] [--embeds EMBED]
               [[COMMAND [ARGS ...]] ...]

information:
  -h [HELP ...], --help [HELP ...]
                        show help message for listed subcommands or main program if none provided (default: None)

logging:
  --logfile LOGFILE     log file (default: None)
  -q, --quite           quite output (default: False)
  --level LEVEL         logging level for output (default: info)

discord:
  settings for the connection

  -e ENV, --env ENV     env file with connection info (default: None)
  -t TOKEN, --token TOKEN
                        Discord API Token. (default: None)
  -g GUILD, --guild GUILD
                        name or id of guild to post to (default: None)
  -c CHANNEL, --channel CHANNEL
                        name or id of channel to post to (default: None)
  --embeds EMBED        file to save embeds to for debugging purposes (default: None)

commands:
  --------
  automate:
    usage: discordcli automate FILE [FILE ...]

    positional arguments:
      FILE  filename to load commands from

  -----
  comic:
    usage: discordcli comic [-n] [-d SQLITE3] [-s FILENAME] [day ...]

    Database and Schedule can be set in an environment file with the keys `DATABASE` and `SCHEDULE` respectively

    positional arguments:
      day                   what days to send

    optional arguments:
      -n, --no-comic        do not send todays comics
      -d SQLITE3, --database SQLITE3
                            filename of the sqlite3 database with the comic info stored in it
      -s FILENAME, --schedule FILENAME
                            filename of json document that contains the list of comics to publish on specific days

  ------
  delete:
    usage: discordcli delete [-f FILE [FILE ...]] [MID ...]

    positional arguments:
      MID                   message ids to delete from channel

    optional arguments:
      -f FILE [FILE ...], --file FILE [FILE ...]
                            message ids to delete from channel

  ----
  edit:
    usage: discordcli edit JSON [JSON ...]

    positional arguments:
      JSON  JSON with info on what messages to edit and how

  ----
  info:
    usage: discordcli info [-q] [filename]

    positional arguments:
      filename     file to save info print to

    optional arguments:
      -q, --quite  don't print info to stdout

  -------
  message:
    usage: discordcli message [-f FILE [FILE ...]] [message ...]

    positional arguments:
      message               send plaintext message

    optional arguments:
      -f FILE [FILE ...], --file FILE [FILE ...]
                            send plaintext contents of a file as a message

  -------
  refresh:
    usage: discordcli refresh [-f FILE [FILE ...]] [MID ...]

    positional arguments:
      MID                   message ids to refresh from channel

    optional arguments:
      -f FILE [FILE ...], --file FILE [FILE ...]
                            file with list of message ids to refresh
```

## Flags / Arguments

### information:
usage: `-h [HELP ...], --help [HELP ...]`  
Passing no arguments displays full help message. Each value passed after that should be
one of the commands. Each value passed will dispaly that specific commands help message.

### logging:
```
--logfile LOGFILE     log file (default: None)
-q, --quite           quite output (default: False)
--level LEVEL         logging level for output (default: info)
```

### discord:
```
-e ENV, --env ENV     env file with connection info (default: None)
-t TOKEN, --token TOKEN
                      Discord API Token. (default: None)
-g GUILD, --guild GUILD
                      name or id of guild to post to (default: None)
-c CHANNEL, --channel CHANNEL
                      name or id of channel to post to (default: None)
--embeds EMBED        file to save embeds to for debugging purposes (default: None)
```
See `environment.sample` for example env file. Keys include:
- `DISCORD_TOKEN`: discord's api token for the bot
- `DISCORD_GUILD`: main guild name or id
- `DISCORD_CHANNEL`: channel name or id to send messages to
- `EMBED`: filepath to save embed dicts to help with debugging

### automate:
usage: `prog automate FILE [FILE ...]`  
Files contain 1 command and it's arguments per line to be run sequentially.
No protection against an automate call inside another file causeing an infinite loop.

### comic:
usage: `prog comic [-n] [-d SQLITE3] [-s FILENAME] [day ...]`  
Accepts a list of days to publish (none listed means just publish todays comics)
`--no-comic` prevents publishing of comics when run, useful for just updating the schedule

Database and Schedule can be set in an environment file with the
keys `DATABASE` and `SCHEDULE` respectively

### delete:
usage: `prog delete [-f FILE [FILE ...]] [MID ...]`  
Delete message ids passed in, files contain 1 message id per line.

### edit:
usage: `prog edit JSON [JSON ...]`  
Pass in JSON file with list of message ids to edit and how to edit them.
Plaintext message will replace old message with the value of `text`. Embeds will
replace the values of the keys that exist with their new ones. So if only `title`
is added only title will be updated, none of the other values will be touched.
Currently only 1 field is supported. Color will be randomly changed.

```json
[
  {
    "mid": 12345,
    "text": "Totally new value"
  },
  {
    "mid": 67890,
    "title":"New Title",
    "url": "https://example.org",
    "image": "https://example.org/image.png",
    "footer": "YYYY-MM-DD",
    "field": {
      "name": "||spoiled hover text||",
      "value": "tag1, tag2, tag3"
    }
  }
]
```

### info:
usage: `prog info [-q] [filename]`  
Print info on bot's connection to discord. This includes the primary guild and channel,
as well as the number of guilds the bot can connect to, their names, and the number of
channels and their names in each guild.
- `filename`: file to save the info to
- `quite`: don't print the output to stdout (ususally used in conjunction with `filename`)

### message:
usage: `prog message [-f FILE [FILE ...]] [message ...]`  
Sends plaintext messages to the primary channel. Each value of `message` is pased as a new
message and files have the whole contents passed as one message.

### refresh:
usage: `prog refresh [-f FILE [FILE ...]] [MID ...]`  
Refresh the color of an embed message to try and get any inbeds (image or video) to load.
Each MID is an embed to refresh and files have 1 message id per line to refresh.

## File / Data Setup
### SQL Comic Database
The Comic Database needs to have at least the following three tables:
```SQL
TABLE Comic(
  release PRIMARY KEY,
  title TEXT NOT NULL,
  image TEXT UNIQUE NOT NULL,
  url TEXT UNIQUE NOT NULL,
);

TABLE Alt(
  comicId REFERENCES Comic(release)
  alt TEXT NOT NULL
);

TABLE Tag(
  comicId REFERENCES Comic(release)
  tag TEXT NOT NULL
);
```

### Schedule File
Schedule File is a json file that dictates which comics get published on each day.
```json
{
  "next_week": "YYYY-MM-DD",
  "days": {
    "YYYY-MM-DD": [ "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD" ],
    "YYYY-MM-DD": [ "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD" ]
  }
}
```
The`next_week` key is used to determine when a weeks of comics has been
published and need to be added to the schedule. It will be a Sunday and
present day(ish). When the date is the same date as now, it'll update
the schedule.

The `days` key is a dictionary used as to lookup what comics to publish on
the key day. The present day gets looked up and the returned list gets passed
to the Comics database.

## License
[The Anti-Capitalist Software License (v 1.4)](https://anticapitalist.software)
