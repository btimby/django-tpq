from __future__ import absolute_import

import mock

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

import tpq

from futures.models import FutureQueue, FutureStat
from futures.futures import (
    Future, FutureResult, JSONSerializer
)
from futures.decorators import future


FAKE_QUEUE = {}


def mock_put(name, message, *args, **kwargs):
    """Fake queue put()."""
    FAKE_QUEUE.setdefault(name, []).append(message)


def mock_get(name, *args, **kwargs):
    """Fake queue get()."""
    try:
        return FAKE_QUEUE[name].pop(0)
    except IndexError:
        raise tpq.QueueEmpty()


def foo(a, b):
    """
    Test function.
    """
    return a + b


def bar(a, b):
    """
    Error function.
    """
    return a / 0


class FutureTestCase(TestCase):
    def test_decorator(self):
        # Create a function for testing.
        def _foo(a, b):
            return a + b

        f_foo = future()(foo)

        # Ensure it is wrapped by Future instance.
        self.assertIsInstance(f_foo, Future)
        self.assertEqual(settings.FUTURES_QUEUE_NAME, f_foo.queue_name)

        # Ensure it is still callable.
        self.assertEqual(8, f_foo(5, 3))

        # Ensure it is named properly.
        self.assertEqual('futures.tests.test_futures.foo', f_foo.name)

    @mock.patch('tpq.put', mock_put)
    @mock.patch('tpq.get', mock_get)
    def test_json(self):
        """Ensure JSON serializer works."""
        f_foo = future(serializer=JSONSerializer)(foo)

        # Run the function in async mode to enqueue it.
        r = f_foo.async(3, 6)
        self.assertIsInstance(r, FutureResult)

        # Ensure we get a dictionary from the queue.
        m = FutureQueue.objects.dequeue()
        self.assertIsInstance(m, dict)
        Future.execute(m)

        # Ensure only one item was in the queue.
        with self.assertRaises(ObjectDoesNotExist):
            FutureQueue.objects.dequeue()

    @mock.patch('tpq.put', mock_put)
    @mock.patch('tpq.get', mock_get)
    def test_async(self):
        """Ensure task hits "queue"."""
        f_foo = future()(foo)

        # Run the function in async mode to enqueue it.
        r = f_foo.async(3, 6)
        self.assertIsInstance(r, FutureResult)

        # Ensure we get a dictionary from the queue.
        m = FutureQueue.objects.dequeue()
        self.assertIsInstance(m, dict)

        # Ensure only one item was in the queue.
        with self.assertRaises(ObjectDoesNotExist):
            FutureQueue.objects.dequeue()

    @mock.patch('tpq.put', mock_put)
    @mock.patch('tpq.get', mock_get)
    def test_execute(self):
        """Ensure task is runnable."""
        f_foo = future()(foo)

        # Run the function in async mode to enqueue it.
        r = f_foo.async(3, 6)

        # Ensure no result is available.
        self.assertIsNone(r.result())

        # This part would be done in the daemon.
        m = FutureQueue.objects.dequeue()
        Future.execute(m)

        self.assertEqual(9, r.result())

    def test_result_timeout(self):
        """Ensure awaiting results times out."""
        f_foo = future()(foo)

        # Run the function in async mode to enqueue it.
        r = f_foo.async(3, 6)

        # Ensure no result is available.
        self.assertIsNone(r.result(wait=0.1))

    @mock.patch('tpq.put', mock_put)
    @mock.patch('tpq.get', mock_get)
    def test_exception(self):
        f_bar = future()(bar)

        with self.assertRaises(ZeroDivisionError):
            f_bar(1, 3)

        # Run the function in async mode to enqueue it.
        r = f_bar.async(3, 6)

        # Ensure no result is available.
        self.assertIsNone(r.result())

        # This part would be done in the daemon.
        m = FutureQueue.objects.dequeue()
        Future.execute(m)

        with self.assertRaises(ZeroDivisionError):
            r.result()

    @mock.patch('tpq.put', mock_put)
    @mock.patch('tpq.get', mock_get)
    def test_stat(self):
        f_foo = future()(foo)
        f_bar = future()(bar)

        f_foo.async(3, 6)
        f_bar.async(3, 6)

        Future.execute(FutureQueue.objects.dequeue())
        Future.execute(FutureQueue.objects.dequeue())

        s_foo = FutureStat.objects.get(name=f_foo.name)
        s_bar = FutureStat.objects.get(name=f_bar.name)

        self.assertEqual(1, s_foo.total)
        self.assertEqual(1, s_bar.total)

        self.assertEqual(0, s_foo.running)
        self.assertEqual(0, s_bar.running)

        self.assertEqual(0, s_foo.failed)
        self.assertEqual(1, s_bar.failed)
