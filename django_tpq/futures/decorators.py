"""
Decorators for django_tpq.
"""
from __future__ import absolute_import

from futures.futures import Future


def future(*args, **kwargs):
    """
    Convert function into Future.
    """
    def decorator(f):
        f = Future(f, *args, **kwargs)
        return f
    return decorator
