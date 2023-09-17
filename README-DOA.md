# Discord DoA Reread and Misc
Discord Reread will upload comics from a week period each day at noon.
It'll also eventually handle commands for info on different characters.

## Instalation
```
pip install -r requirements.txt
```

### Requires
- `py-cord`: 2.0.0a
- `python-dotenv`: 0.18.0

## Usage
Include the `doa` folder somewhere for a Discord bot to load with
the `load_extension` command, the `setup` method in `__init__` will
add the it as a cog to the bot.


## Environment Values
See `environment.sample` for example env file. Keys include:
- `DATABASE`: database of comic stuff
- `SCHEDULE`: schedule db filename
- `EMBEDS`: embeds id filename


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

## Links
* [Git Repo](https://git.whatno.io/discord/doa)

## Contributing
Help is greatly appreciated. First check if there are any issues open that relate to what you want
to help with. Also feel free to make a pull request with changes / fixes you make.

## License
[MIT License](https://opensource.org/licenses/MIT)
