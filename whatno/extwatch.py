"""Watch for changes in the extensions for Discord"""
import logging
from pathlib import Path
from sys import exc_info
from traceback import format_tb
from threading import Timer

from discord import (
    ExtensionNotFound,
    ExtensionAlreadyLoaded,
    NoEntryPointError,
    ExtensionFailed,
    ExtensionNotLoaded,
)
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ExtensionWatcher:
    """Watch discord extensions for chagnes to reload them"""

    def __init__(self, path, bot):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.path = path
        self.event_handler = ExtensionEventHandler(bot=bot, root=path)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, path, recursive=True)

    def stop(self):
        """Stop watcher"""
        self.event_handler.timer.cancel()
        self.observer.stop()
        self.event_handler.timer.join()

    def watch(self, event):
        """Start watching the extensions"""
        self.observer.start()
        if event.wait():
            self.stop()


class ExtensionEventHandler(FileSystemEventHandler):
    """Handle changes to extensions folder"""

    def __init__(self, bot=None, root=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.bot = bot
        self.module = str(Path(root)).replace("/", ".")
        self.root = Path(root).resolve()
        self.loadthis = set()
        self.deletethis = set()
        self.movethis = set()
        for filename in self.root.glob("*"):
            if filename.match("__pycache__"):
                continue
            rel = self._gen_module(filename)
            self._load(rel)
        self.timer = Timer(1.0, self._update_bot)
        self.timer.start()

    @staticmethod
    def _abs_src(src):
        src = Path(src)
        if src.is_symlink():
            src = src.parent.resolve() / src.name
            suffix = src.resolve().suffix
        else:
            src = src.resolve()
            suffix = src.suffix
        return src, suffix

    def _gen_module(self, src):
        rec, _ = self._abs_src(src)
        rel = rec.relative_to(self.root).stem
        return ".".join([self.module, rel])

    def _load(self, module):
        try:
            self.bot.load_extension(module)
        except ExtensionAlreadyLoaded:
            self.bot.reload_extension(module)
        except (
            ExtensionNotFound,
            NoEntryPointError,
            ExtensionFailed,
        ) as e:
            _, _, err_traceback = exc_info()
            tb_list = "\n".join(format_tb(err_traceback))
            tb_str = " | ".join(tb_list.splitlines())
            self._logger.info("load? %s: %s | %s", module, e, tb_str)

    def _unload(self, module):
        try:
            self.bot.unload_extension(module)
        except (
            ExtensionNotFound,
            ExtensionNotLoaded,
            KeyError,
        ) as e:
            _, _, err_traceback = exc_info()
            tb_list = "\n".join(format_tb(err_traceback))
            tb_str = " | ".join(tb_list.splitlines())
            self._logger.info("unload? %s: %s | %s", module, e, tb_str)

    def _update_bot(self):
        self.loadthis = self.loadthis - self.deletethis - self.movethis
        if self.loadthis:
            for ext in self.loadthis:
                mod = self._gen_module(ext)
                self._load(mod)
                self._logger.info("loading » %s", mod)
            self.loadthis = set()
        if self.movethis:
            for s_ext, d_ext in self.movethis:
                s_mod = self._gen_module(s_ext)
                d_mod = self._gen_module(d_ext)
                self._unload(s_mod)
                self._load(d_mod)
                self._logger.info("move » %s -> %s", s_mod, d_mod)
            self.movethis = set()
        if self.deletethis:
            for ext in self.deletethis:
                mod = self._gen_module(ext)
                self._unload(mod)
                self._logger.info("unload » %s", mod)
            self.deletethis = set()
        self.timer = Timer(1.0, self._update_bot)
        self.timer.start()

    def _do_file(self, src):
        rel = src.relative_to(self.root)
        src, suffix = self._abs_src(src)

        isdir = src.is_dir() or (src.is_symlink() and src.resolve().is_dir())
        valid = str(rel) not in (".", "__pycache__") and (
            list(src.glob("*.py")) if isdir else (suffix == ".py")
        )

        return valid, rel

    def on_created(self, event):
        """Handle a 'created' event"""
        src = Path(event.src_path)
        valid, rel = self._do_file(src)
        if valid:
            self.loadthis.add(src)
            self._logger.info("created: %s", rel)

    def on_deleted(self, event):
        """Handle a 'deleted' event"""
        src = Path(event.src_path)
        valid, rel = self._do_file(src)
        if valid:
            self.deletethis.add(src)
            self._logger.info("deleted: %s", rel)

    def on_modified(self, event):
        """Handle a 'modified' event"""
        src = Path(event.src_path)
        valid, rel = self._do_file(src)
        if valid:
            self.loadthis.add(src)
            self._logger.info("modified: %s", rel)

    def on_moved(self, event):
        """Handle a 'moved' event"""
        src = Path(event.src_path)
        dest = Path(event.dest_path)
        s_valid, s_rel = self._do_file(src)
        d_valid, d_rel = self._do_file(dest)
        if s_valid and d_valid:
            self.movethis.add((src, dest))
            self._logger.info("moved: %s -> %s", s_rel, d_rel)
        elif s_valid and not d_valid:
            self.deletethis.add(src)
