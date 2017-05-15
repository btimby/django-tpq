from django.core.management import call_command
from django.test import TestCase

from futures.decorators import future


@future()
def foo(a, b):
    return a + b


class TestExecutor(TestCase):
    """
    Test executor command.

    Basically a full-stack test. We declare a future using our decorator, write
    it to an actual queue, execute it with the Django management command, then
    verify the result.
    """
    def test_command(self):
        # Queue up a future.
        r = foo.async(3, 9)

        # Execute it.
        call_command('futures_executor', once=True, wait=0)

        # Make sure our function was called.
        self.assertEqual(12, r.result())
