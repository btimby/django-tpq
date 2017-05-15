"""
Future implementation.
"""
from __future__ import absolute_import

import uuid
import time
import pickle

from base64 import b64encode, b64decode

from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.db.models import F
from django.utils import timezone

import tpq

from futures.models import FutureStat
from futures.models import FutureQueue


DEFAULT_QUEUE_NAME = 'futures.FutureQueue'


def set_result(uid, obj, progress=0):
    """Place Future results into cache."""
    if isinstance(obj, Exception):
        # TODO: store backtrace etc.
        pass
    obj = pickle.dumps(obj)
    result = {
        'uid': uid,
        'obj': obj,
        'ts': time.time(),
        'progress': progress,
    }
    cache = caches[settings.FUTURES_CACHE_BACKEND]
    cache.set('futures:%s' % uid, result, settings.FUTURES_CACHE_TTL)


def get_result(uid):
    """Retrieve Future results from cache."""
    cache = caches[settings.FUTURES_CACHE_BACKEND]
    result = cache.get('futures:%s' % uid)
    if result is None:
        return
    # TODO: how do we want to report/represent progress?
    obj = pickle.loads(result['obj'])
    if isinstance(obj, Exception):
        raise obj
    return obj


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

    @property
    def name(self):
        return '%s.%s' % (self.f.__module__, self.f.__name__)

    def async(self, *args, **kwargs):
        """
        Schedule a Future for execution.
        """
        uid = str(uuid.uuid4())
        message = {
            'uid': uid,
            'self': pickle.dumps(self, 0).decode('latin-1'),
            'args': pickle.dumps(args, 0).decode('latin-1'),
            'kwargs': pickle.dumps(kwargs, 0).decode('latin-1'),
        }
        label, _, model = self.queue_name.partition('.')
        Model = apps.get_model(app_label=label, model_name=model)
        Model.objects.enqueue(message)
        return FutureResult(uid, self)

    @staticmethod
    def execute(message):
        """
        Used by task runner to execute a Future.

        Manages FutureStat.
        """
        t = pickle.loads(message['self'].encode('latin-1'))
        args = pickle.loads(message['args'].encode('latin-1'))
        kwargs = pickle.loads(message['kwargs'].encode('latin-1'))

        stat, _ = FutureStat.objects.get_or_create(name=t.name)
        stat.update(last_seen=timezone.now(), total=F('total') + 1,
                    running=F('running') + 1)

        failed = {}
        try:
            try:
                r = t(*args, **kwargs)
            except Exception as e:
                failed['failed'] = F('failed') + 1
                set_result(message['uid'], e)
            else:
                set_result(message['uid'], r)
        finally:
            stat.update(running=F('running') - 1, **failed)


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
        while True:
            result = get_result(self.uid)
            if result is not None:
                return result
            if timeout == 0:
                break
            if timeout > 0:
                timeout -= 1
            time.sleep(1.0)
