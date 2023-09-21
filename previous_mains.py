# Instadown
# TODO: Move testing into a testing folder / lib
if __name__ == "__main__":
    # pylint: disable=ungrouped-imports
    from asyncio import run
    from sys import argv

    storage = Path(argv[1]).resolve()
    request = argv[2]

    # pylint: disable=too-few-public-methods
    class DummyBot:
        """Fake the Discord Bot for testing the cog"""

        def __init__(self):
            self.storage = storage

    cog = InstaDownCog(DummyBot())
    result, errors = run(cog.download(request, [], []))
    print(result)
    print(errors)



# Snaplookup
# TODO: Move mains into a test module
if __name__ == "__main__":
    import sys
    # pylint: disable=ungrouped-imports
    from asyncio import run
    from datetime import datetime
    from os import environ
    from pathlib import Path

    from helpers import CleanHTML, PrettyStringDB, aget_json, calc_path, strim

    storage = Path(sys.argv[1]).resolve()
    matched = re.findall(r"\{\{.*?\}\}", sys.argv[2], flags=re.IGNORECASE)
    if not matched:
        print("no matched")
        sys.exit(1)

    # pylint: disable=too-few-public-methods,invalid-name
    class DummyGuild:
        """Mock the Guild class for testing purposes"""
        def __init__(self):
            self.id = "gid"

    # pylint: disable=too-few-public-methods,invalid-name
    class DummyChannel:
        """Mock the Channel class for testing purposes"""
        def __init__(self):
            self.id = "cid"

    # pylint: disable=too-few-public-methods,invalid-name
    class DummyAuthor:
        """Mock the Author class for testing purposes"""
        def __init__(self):
            self.id = "aid"

    # pylint: disable=too-few-public-methods
    class DummyMessage:
        """Mock the Message class for testing purposes"""
        def __init__(self):
            self.guild = DummyGuild()
            self.channel = DummyChannel()
            self.id = "mid"
            self.author = DummyAuthor()
            self.created_at = datetime.now()

    # pylint: disable=too-few-public-methods
    class DummyEnv:
        """Mock the Env class for testing purposes"""
        def __init__(self):
            pass

        @staticmethod
        def path(name, default):
            """Create Path from env variable"""
            return Path(environ.get("DISCORD_SNAPLOOKUP_" + name, default))

    # pylint: disable=too-few-public-methods
    class DummyBot:
        """Mock the Bot class for testing purposes"""
        def __init__(self):
            self.storage = storage
            self.env = DummyEnv()

    cog = SnapCog(DummyBot())
    result = cog.get_requests(matched, DummyMessage())
    print(result)

    snapdir_dir = storage / "snaplookup"
    combo_dir = snapdir_dir / "combo"
    info = DummyEnv.path("DISCORD_SNAPDB", "data.db")
    database = PrettyStringDB(info)
    run(SnapData(snapdir_dir, combo_dir, database).process(dnld=True))
