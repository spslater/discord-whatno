[![github](https://img.shields.io/badge/GitHub-Discord_Whatno_Bot-blue?logo=github&link=https%3A%2F%2Fwww.github.com%2Fspslater%2Fdiscord-whatno)](https://www.github.com/spslater/discord-what)
![stars](https://img.shields.io/github/stars/spslater/discord-whatno)
![commits](https://img.shields.io/github/commit-activity/t/spslater/discord-whatno)
![issues](https://img.shields.io/github/issues/spslater/discord-whatno)
![repo size](https://img.shields.io/github/repo-size/spslater/discord-whatno)
![license](https://img.shields.io/github/license/spslater/discord-whatno)

# Whatno Discord Bot
Generic Discord bot to run the different things I want it to run...

## Instalation
Requires at least Python 3.11 (it's what I test on and run but it may run on earlier versions)
```bash
pip install -r requirements.txt
```
See [requirements.txt](requirements.txt) file for specific packages.


## Running
Command line args will override values in the `.env` file.

```
usage: whatno [-h] [-o FILENAME] [-q] [-l LEVEL] [-e ENV] [-t TOKEN]

optional arguments:
  -h, --help            show this help message and exit
  -o FILENAME, --output FILENAME
                        log file
  -q, --quite           quite output
  -l LEVEL, --level LEVEL
                        logging level for output
  -e ENV, --env ENV     env file with connection info
  -t TOKEN, --token TOKEN
                        Discord API Token.
```

## Cogs
### DoA Comic
Track voted scores and comic info to get tag stats and the like.

### Instadown
Download short videos from Instagram, YouTube, and some other sites to share easier.

### Snap Lookup
View Marvel Snap cards and locations and their text.

### Stats
Track voice time, message numbers, and others to create a leaderboard.

### WN Message
Send a message as the bot from within discord

### WN Test
Basic ping/pong test to see if the bot is up

## Contributing
Help is greatly appreciated. First check if there are any issues open that relate to what you want
to help with. Also feel free to make a pull request with changes / fixes you make.

## License
[MIT License](https://opensource.org/licenses/MIT)
