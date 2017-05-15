import multiprocessing
import time
import threading
import unittest

from django.core.management import call_command
from django.test import TransactionTestCase

from futures.decorators import future
from futures.models import FutureStat


@future()
def foo(a, b):
    return a + b


# We use TransactionTestCase to ensure our queue is visible to another
# connection/thread/process.
class TestExecutor(TransactionTestCase):
    """
    Test executor command.
    """

    def setUp(self):
        FutureStat.objects.all().delete()

    tearDown = setUp

    def test_command(self):
        """
        Basically a full-stack test. We declare a future using our decorator,
        write it to an actual queue, execute it with the Django management
        command, then verify the result. We also check that stats are properly
        updated for the future.
        """
        # Queue up a future.
        r = foo.async(3, 9)

        # Execute it.
        p = multiprocessing.Process(target=call_command,
                                    args=('futures_executor',),
                                    kwargs={
                                        'processes': 1,
                                        'threads': 1,
                                        'restart': False,
                                        'limit': 1,
                                        'wait': 0,
                                    })
        p.start()
        p.join()

        try:
            # Make sure our function was called.
            self.assertEqual(12, r.result())
        finally:
            p.terminate()
            p.join()

        stat = FutureStat.objects.get(name=foo.name)
        self.assertEqual(1, stat.total)
        self.assertEqual(0, stat.failed)
        self.assertEqual(0, stat.running)

    @unittest.skip('Causes an error (connections left open somehow).')
    def test_stress(self):
        """
        A little stress test to push a bunch of Futures through and check the
        results.
        """
        count, results = 1024, []

        def _make_producer(low, high):
            def _produce():
                for i in range(low, high):
                    results.append((i, foo.async(i, 1)))
            return _produce

        p = multiprocessing.Process(target=call_command,
                                    args=('futures_executor',),
                                    kwargs={
                                        'processes': 3,
                                        'threads': 3,
                                        'restart': True,
                                        'limit': 10,
                                        'wait': -1,
                                    })
        p.start()

        start = time.time()
        try:

            t1 = threading.Thread(target=_make_producer(0, int(count / 2)))
            t1.start()
            t2 = threading.Thread(target=_make_producer(int(count / 2), count))
            t2.start()
            t1.join()
            t2.join()

            print('\nStress test enqueue wall time: %s' %
                  (time.time() - start))

            self.assertEqual(count, len(results))
            for i, r in results:
                self.assertEqual(i + 1, r.result(wait=-1))

            print('\nStress test dequeue wall time: %s' %
                  (time.time() - start))

        finally:
            p.terminate()
            p.join()

        stat = FutureStat.objects.get(name=foo.name)
        self.assertEqual(count, stat.total)
        self.assertEqual(0, stat.failed)
        self.assertEqual(0, stat.running)
