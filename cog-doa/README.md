# Discord Reread
Discord Reread will upload comics from a week period each time it's run.

## Instalation
```
pip install -r requirements.txt
```

## Running
The bot only needs permission to Send Messages to a server to operate.

Command line args will override values in the `.env` file.

```shell
usage: rewatchbot.py [-h] [-l LOGFILE] [-q] [--mode MODE] [-e, --env ENV]
                     [-d, --database SQLITE3] [-t TOKEN] [-gn GUILDNAME]
                     [-gi GUILDID] [-cn CHANNELNAME] [-ci CHANNELID]
                     [-w YYYY-MM-DD] [-wf WEEKFILE]

optional arguments:
  -h, --help            show this help message and exit
  -l LOGFILE, --log LOGFILE
                        Log file. (default: None)
  -q, --quite           Quite output (default: False)
  --mode MODE           Logging level for output (default: INFO)
  -e, --env ENV         Environment file to load. (default: .env)
  -d, --database SQLITE3
                        Sqlite3 database with comic info. (default: None)
  -t TOKEN, --token TOKEN
                        Discord API Token. (default: None)
  -gn GUILDNAME, --guild-name GUILDNAME
                        Name of Guild to post to. (default: None)
  -gi GUILDID, --guild-id GUILDID
                        Id of Guild to post to. (default: None)
  -cn CHANNELNAME, --channel-name CHANNELNAME
                        Name of Guild to post to. (default: None)
  -ci CHANNELID, --channel-id CHANNELID
                        Id of Guild to post to. (default: None)
  -w YYYY-MM-DD, --week YYYY-MM-DD
                        Date to pull week of comics from. (default: None)
  -wf WEEKFILE, --weekfile WEEKFILE
                        File to load midweek date from. If week is passed in,
                        this file will be ignore. (default: midweek.txt)
```

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

### Env File
To load everything from the env file the following keys are needed:
```
DISCORD_TOKEN=<str>
CHANNEL_NAME=<str>
CHANNEL_ID=<int>
GUILD_NAME=<str>
GUILD_ID=<int>
DATABASE=<path>
```

### Midweek File
Midweek file just needs the date in it in the format `%Y-%m-%d`
```
2010-10-09
```

## License
[The Anti-Capitalist Software License (v 1.4)](https://anticapitalist.software)
