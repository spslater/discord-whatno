# Whatno Discord Bot
Generic Discord bot to run the different things I want it to run...

## Instalation
```
pip install -r requirements.txt
```

Requires:
- `py-cord`: 2.0.0a
- `python-dotenv`: 0.18.0


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


## Links
* [Git Repo](https://git.whatno.io/discord/whatno)

## Contributing
Help is greatly appreciated. First check if there are any issues open that relate to what you want
to help with. Also feel free to make a pull request with changes / fixes you make.

## License
[MIT License](https://opensource.org/licenses/MIT)
