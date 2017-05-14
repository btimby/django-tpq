from __future__ import absolute_import

import mock

from django.test import TestCase

from futures import Future
from futures.decorators import future

from tpq import QueueEmpty


FAKE_QUEUE = {}


def mock_put(name, message):
    """Fake queue put()."""
    FAKE_QUEUE.setdefault(name, []).append(message)


def mock_get(name):
    """Fake queue get()."""
    try:
        return FAKE_QUEUE[name].pop(0)
    except IndexError:
        raise QueueEmpty()


def foo(a, b):
    """
    Test function.
    """
    return a + b


class FutureTestCase(TestCase):
    def test_decorator(self):
        # Create a function for testing.
        def _foo(a, b):
            return a + b

        f_foo = future(queue_name='foo_queue')(foo)

        # Ensure it is wrapped by Future instance.
        self.assertIsInstance(f_foo, Future)
        self.assertEqual('foo_queue', f_foo.queue_name)

        # Ensure it is still callable.
        self.assertEqual(8, f_foo(5, 3))

    @mock.patch('tpq.put', mock_put)
    def test_delay(self):
        f_foo = future(queue_name='foo_queue')(foo)
        r = f_foo.delay(3, 6)
        m = mock_get('foo_queue')