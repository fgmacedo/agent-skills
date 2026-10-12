"""Start coverage.py inside a long-running production process.

Import this module at the common entry point of every service and call
``start()`` after the process has forked (uwsgi ``@postfork``, gunicorn
``post_fork``, the top of a worker or cron job ``main``). Nothing happens
unless the ``DEADCODE_COVERAGE`` environment variable is set, so the same
image runs with and without collection.

Runs on coverage 5.5 / Python 2.7 and on coverage 7.x / Python 3.

Environment variables (all optional except the first):

    DEADCODE_COVERAGE=1                  enable collection
    DEADCODE_COVERAGE_DATA_FILE=path     base data file (default: ./.coverage)
    DEADCODE_COVERAGE_SOURCE=pkg,other   packages to measure (default: all)
    DEADCODE_COVERAGE_INTERVAL=300       seconds between periodic saves
    DEADCODE_COVERAGE_CONCURRENCY=thread coverage ``concurrency`` option
    DEADCODE_COVERAGE_SIGNALS=TERM,INT   signals that trigger a save

Example::

    from coverage_bootstrap import start

    def upload(path):
        bucket.upload_file(path, "coverage/%s/%s" % (SERVICE, os.path.basename(path)))

    recorder = start(upload=upload)
"""
from __future__ import print_function

import atexit
import logging
import os
import signal
import threading

ENV_ENABLE = "DEADCODE_COVERAGE"
ENV_DATA_FILE = "DEADCODE_COVERAGE_DATA_FILE"
ENV_SOURCE = "DEADCODE_COVERAGE_SOURCE"
ENV_INTERVAL = "DEADCODE_COVERAGE_INTERVAL"
ENV_CONCURRENCY = "DEADCODE_COVERAGE_CONCURRENCY"
ENV_SIGNALS = "DEADCODE_COVERAGE_SIGNALS"

DEFAULT_INTERVAL = 300.0
DEFAULT_SIGNALS = ("TERM",)

log = logging.getLogger("coverage_bootstrap")


def _split(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_signals(default):
    raw = os.environ.get(ENV_SIGNALS)
    names = _split(raw) if raw else list(default)
    found = []
    for name in names:
        attr = name if name.startswith("SIG") else "SIG" + name
        number = getattr(signal, attr, None)
        if number is not None:
            found.append(number)
    return found


class Recorder(object):
    def __init__(self, cov, interval, upload, signals):
        self.cov = cov
        self.interval = interval
        self.upload = upload
        self.signals = signals
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._timer = None
        self._previous_handlers = {}

    @property
    def data_file(self):
        data = self.cov.get_data()
        if hasattr(data, "data_filename"):
            return data.data_filename()
        return data.filename

    def start(self):
        self.cov.start()
        atexit.register(self.save)
        self._install_signal_handlers()
        self._install_uwsgi_hook()
        if self.interval and self.interval > 0:
            self._timer = threading.Thread(target=self._periodic_save)
            self._timer.daemon = True
            self._timer.start()
        log.info("coverage started, data file %s", self.data_file)
        return self

    def save(self):
        with self._lock:
            try:
                self.cov.save()
            except Exception:
                log.exception("coverage save failed")
                return
            if self.upload is not None:
                try:
                    self.upload(self.data_file)
                except Exception:
                    log.exception("coverage upload failed")

    def stop(self):
        self._stop_event.set()
        try:
            self.cov.stop()
        except Exception:
            log.exception("coverage stop failed")
        self.save()

    def _periodic_save(self):
        while not self._stop_event.wait(self.interval):
            self.save()

    def _install_signal_handlers(self):
        for signum in self.signals:
            try:
                self._previous_handlers[signum] = signal.signal(signum, self._on_signal)
            except (ValueError, OSError, RuntimeError) as exc:
                log.warning("cannot install handler for signal %s: %s", signum, exc)

    def _on_signal(self, signum, frame):
        self.stop()
        previous = self._previous_handlers.get(signum)
        if callable(previous):
            previous(signum, frame)
            return
        if previous == signal.SIG_IGN:
            return
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _install_uwsgi_hook(self):
        try:
            import uwsgi
        except ImportError:
            return
        previous = getattr(uwsgi, "atexit", None)

        def on_exit():
            self.stop()
            if callable(previous):
                previous()

        uwsgi.atexit = on_exit


def start(data_file=None, source=None, interval=None, upload=None,
          concurrency=None, signals=None, context=None, enabled=None):
    """Start coverage if enabled; return a Recorder or None.

    Call it in the child process, after any fork. Every argument falls back to
    the matching DEADCODE_COVERAGE_* variable.
    """
    if enabled is None:
        enabled = bool(os.environ.get(ENV_ENABLE))
    if not enabled:
        return None

    import coverage

    if data_file is None:
        data_file = os.environ.get(ENV_DATA_FILE) or os.path.abspath(".coverage")
    if source is None and os.environ.get(ENV_SOURCE):
        source = _split(os.environ[ENV_SOURCE])
    if interval is None:
        interval = float(os.environ.get(ENV_INTERVAL, DEFAULT_INTERVAL))
    if concurrency is None:
        concurrency = os.environ.get(ENV_CONCURRENCY) or None
    if signals is None:
        signals = _env_signals(DEFAULT_SIGNALS)

    directory = os.path.dirname(os.path.abspath(data_file))
    if not os.path.isdir(directory):
        os.makedirs(directory)

    kwargs = dict(data_file=data_file, data_suffix=True, source=source,
                  concurrency=concurrency)
    if context is not None:
        kwargs["context"] = context
    cov = coverage.Coverage(**kwargs)
    return Recorder(cov, interval, upload, signals).start()
