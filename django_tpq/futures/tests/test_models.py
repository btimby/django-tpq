from django.test import TestCase

from futures.models import FutureQueue, FutureStat


D = {'foo': 'foo'}


class TestManager(TestCase):
    def test_not_implemented(self):
        """Test manager extraneous methods."""
        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.get()

        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.create()

        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.get_or_create()

        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.filter()

        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.all()

        with self.assertRaises(NotImplementedError):
            FutureQueue.objects.first()


class TestModel(TestCase):
    def setUp(self):
        FutureQueue.objects.clear()

    tearDown = setUp

    def test_enqueue(self):
        """Test enqueuing."""
        o = object()
        # Cannot enqueue arbirary objects.
        with self.assertRaises(AssertionError):
            FutureQueue.objects.enqueue(o)
        # Only dicts
        FutureQueue.objects.enqueue({'foo': 'foo'})

    def test_dequeue(self):
        FutureQueue.objects.enqueue(D)
        d = FutureQueue.objects.dequeue()
        self.assertEqual(D, d)
