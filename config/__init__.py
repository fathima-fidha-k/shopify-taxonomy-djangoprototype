"""
Import the Celery app here so `celery -A config worker` and Django both find
it. Celery is an OPTIONAL dependency (see requirements.txt) needed only for
`--async` batch dispatch (README Priority 7). Every other feature -- the
sync classify_catalogue command, the API, the dashboard -- must keep
working with zero Celery/Redis installed, since that's the default,
zero-install path most reviewers will actually run.

If you see `ModuleNotFoundError: No module named 'celery'` anywhere, it
means something tried to actually USE Celery (e.g. running
`celery -A config worker` without having run `pip install celery[redis]`
first) -- that's expected and correct, not a bug in this guard. This guard
only prevents Celery being *required* just to start Django normally.
"""

try:
    from config.celery import app as celery_app
except ImportError:
    # Celery isn't installed -- fine, only `--async` mode and the worker
    # process need it. Everything else in this project runs without it.
    celery_app = None

__all__ = ("celery_app",)
