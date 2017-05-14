"""
Future implementation.
"""
from __future__ import absolute_import

import uuid
import pickle

import tpq


DEFAULT_QUEUE_NAME = 'futures'


class Future(object):
    """
    Manage a function call as a Future.
    """

    def __init__(self, f, queue_name=DEFAULT_QUEUE_NAME):
        self.f = f
        self.queue_name = queue_name

    def __call__(self, *args, **kwargs):
        """
        Call the function normally.
        """
        return self.f(*args, **kwargs)

    def delay(self, *args, **kwargs):
        """
        Schedule a Future for execution.
        """
        uid = str(uuid.uuid4())
        message = {
            'uid': uid,
            'self': pickle.dumps(self),
            'args': pickle.dumps(args),
            'kwargs': pickle.dumps(kwargs),
        }
        tpq.put(self.queue_name, message)
        return FutureResult(uid, self)

    @staticmethod
    def execute(message):
        """
        Used by task runner to execute a Future.
        """
        t = pickle.loads(message['self'])
        args = pickle.loads(message['args'])
        kwargs = pickle.loads(message['kwargs'])

        try:
            r = t(*args, **kwargs)
        except Exception as e:
            results.put(message['uid'], e)
        else:
            results.put(message['uid'], r)


class FutureResult(object):
    """
    Handle Future results.
    """

    def __init__(self, uid, task):
        self.uid = uid
        self.task = task

    def wait(self, timeout=0):
        """
        Wait for Future results.
        """
        # TODO: use polling or LISTEN/NOTIFY to await results.
        pass
