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
                     [-s FILENAME] [-nc] [-i] [-if FILENAME] [-m MESSAAGE]
                     [-mf FILENAME]

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
  -s FILENAME, --schedule FILENAME
                        JSON file to load release information from. (default:
                        None)
  -nc, --no-comics      Do not send the weekly comics to the server. (default:
                        True)
  -i, --info            Print out availble guilds and channels and other
                        random info I add. Prints to stdout, not the log file.
                        (default: False)
  -if FILENAME, --info-file FILENAME
                        File to save info print to, won't print to stdout if
                        set and -i flag not used. (default: None)
  -m MESSAAGE, --message MESSAAGE
                        Send a plaintext message to the configured channel
                        (default: None)
  -mf FILENAME, --message-file FILENAME
                        Send plaintext contents of a file as a message to the
                        configured channel (default: None)
```

## Non Comic Sending Stuff
### No Comics
The `-nc, --no-comics` arguments prevent the comics getting sent to the server.
This should be used for when you just want a message to be sent or to print out
the bot info.

### Information
The `-i, --info` flag will print out guild and channel info for the bot. The
`-if, --info-file` will save that data to the specificed file. These are
independent actions. So passing just the `-if` flag will only save it to the file,
passing just the `-i` flag only prints to stdout, and passing both will do both
actions.

### Messages
The `-m, --message` flag sends the string as a plaintext message to the configured
channel. This follows Discords standard limited markdown formatting.
The `-mf, --message-file` flag loads the conents of a file and sends that as a
plaintext markdown formatted message, just like the `-m` flag. When both flags
are used, the `-m` message gets sent first then the contents of the file.


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
SCHEDULE=<path>
```

### Schedule File
Schedule File is a json file that dictates which comics get published on each day.
```json
{
  'next_week': 'YYYY-MM-DD',
  'days': {
    'YYYY-MM-DD': [ 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD' ],
    'YYYY-MM-DD': [ 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD' ]
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


