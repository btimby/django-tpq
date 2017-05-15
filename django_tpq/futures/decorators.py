"""
Decorators for django_tpq.
"""
from __future__ import absolute_import

from futures.futures import (
    Future, FUTURES_REGISTRY
)


def future(*args, **kwargs):
    """
    Convert function into Future.
    """
    def decorator(f):
        # Wrap the function in a Future object.
        wrapped = Future(f, *args, **kwargs)

        # Register the future object.
        FUTURES_REGISTRY[wrapped.name] = wrapped

        # Return the future object.
        return wrapped

    return decorator
