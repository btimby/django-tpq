"""
Future implementation.
"""
from __future__ import absolute_import

import abc
import functools
import json
import logging
import sys
import time
import uuid

import dill

from tblib import Traceback

from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.db.models import F
from django.utils import timezone

from futures.models import FutureStat


LOGGER = logging.getLogger(__name__)
FUTURES_REGISTRY = {}


def set_result(uid, obj, progress=0):
    """Place Future results into cache."""
    if isinstance(obj, tuple) and isinstance(obj[1], Exception):
        # Wrap the tb so it can be transported and re-raised.
        et, ev, tb = obj
        obj = (et, ev, Traceback(tb))
    obj = dill.dumps(obj)
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
    # TODO: how do we want to report/represent progress? One idea is to use a
    # generator such that each future function yields it's progress, and we
    # update the result with that progress.
    obj = dill.loads(result['obj'])
    if isinstance(obj, tuple) and isinstance(obj[1], Exception):
        # Unpack and reraise the exception.
        et, ev, tb = obj
        raise ev.with_traceback(tb.as_traceback())
    return obj


def get_queue_model(queue_name):
    label, _, model = queue_name.partition('.')
    return apps.get_model(app_label=label, model_name=model)


class BaseSerializer(object):
    """
    Abstract base class for serializers.

    Derive from this to implement other serialization methods such as protobuf,
    msgpack etc.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def serialize(self, obj):
        """Convert obj to plain text."""
        pass

    @abc.abstractmethod
    def deserialize(self, blob):
        """Convert blob into object."""
        pass


class DillSerializer(BaseSerializer):
    """
    Serializer for use with complex data types.

    Can serialize any Python object.
    """

    def serialize(self, obj):
        """Convert obj to plain text."""
        return dill.dumps(obj, 0).decode('latin-1')

    def deserialize(self, blob):
        """Convert blob into object."""
        return dill.loads(blob.encode('latin-1'))


class JSONSerializer(BaseSerializer):
    """
    Serializer for use with simple data types.

    Useful for integrating with non-python systems. For example node.js as a
    producer.
    """

    def serialize(self, obj):
        """Convert obj to plain text."""
        return json.dumps(obj)

    def deserialize(self, blob):
        """Convert blob into object."""
        return json.loads(blob)


class Future(object):
    """
    Manage a function call as a Future.
    """

    def __init__(self, f, queue_name=settings.FUTURES_QUEUE_NAME,
                 serializer=DillSerializer):
        self.f = f
        self.serializer = serializer()
        self.queue_name = queue_name
        functools.update_wrapper(self, f)

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
            'name': self.name,
            'args': self.serializer.serialize(args),
            'kwargs': self.serializer.serialize(kwargs),
        }
        Model = get_queue_model(self.queue_name)
        Model.objects.enqueue(message)
        return FutureResult(uid, self)

    @staticmethod
    def execute(message):
        """
        Used by task runner to execute a Future.

        Manages FutureStat.
        """
        future = FUTURES_REGISTRY.get(message['name'])
        args = future.serializer.deserialize(message['args'])
        kwargs = future.serializer.deserialize(message['kwargs'])

        stat, _ = FutureStat.objects.get_or_create(name=future.name)
        stat.update(last_seen=timezone.now(), total=F('total') + 1,
                    running=F('running') + 1)

        failed = {}
        try:
            try:
                r = future(*args, **kwargs)
            except:
                LOGGER.warning('Future exception in %s', future.name,
                               exc_info=True)
                failed['failed'] = F('failed') + 1
                set_result(message['uid'], sys.exc_info())
            else:
                LOGGER.debug('Future success %s', future.name)
                set_result(message['uid'], r)
        finally:
            stat.update(running=F('running') - 1, **failed)

        # TODO: we may wish to do a NOTIFY here to inform any result() waiters
        # that data may be available for them.


class FutureResult(object):
    """
    Handle Future results.
    """

    def __init__(self, uid, task):
        self.uid = uid
        self.task = task

    def result(self, timeout=0):
        """
        Wait for Future results.
        """
        while True:
            # TODO: I don't like polling, we could use LISTEN here, even
            # globally so that any waiters would check if their future was
            # complete. Even if all were awakened for each completed future, it
            # would be more efficient than polling.
            result = get_result(self.uid)
            if result is not None:
                return result
            if timeout == 0:
                break
            if timeout > 0:
                timeout -= 1
            time.sleep(1.0)
