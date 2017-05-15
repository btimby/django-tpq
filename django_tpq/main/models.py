from django.db import models
from django.db import connections
from django.db.transaction import atomic
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ObjectDoesNotExist

import tpq


class BaseQueueManager(models.Manager):
    """
    Queue Manager.

    Allows interaction with queue via tpq methods.
    """

    def create(self, *args, **kwargs):
        """
        Disable these ORM methods.
        """
        raise NotImplementedError('Use enqueue(), dequeue(), clear() and '
                                  'count() to interact with queue')

    # More disabled methods.
    all = create
    get = create
    first = create
    filter = create
    get_or_create = create

    @atomic
    def enqueue(self, d):
        """
        Add an item to the queue.
        """
        assert isinstance(d, dict), 'Must enqueue a dictionary'
        tpq.put(self.model._meta.db_table, d, conn=connections[self.db])

    @atomic
    def dequeue(self, wait=-1):
        """
        Return a single item from the queue, optionally waiting.
        """
        try:
            return tpq.get(self.model._meta.db_table, wait=wait,
                           conn=connections[self.db])
        except tpq.QueueEmpty:
            raise ObjectDoesNotExist

    @atomic
    def clear(self):
        """
        Delete all items from the queue.
        """
        tpq.clear(self.model._meta.db_table, conn=connections[self.db])

    @atomic
    def count(self):
        """
        Counts items in the queue.
        """
        return tpq.count(self.model._meta.db_table, conn=connections[self.db])


class BaseQueue(models.Model):
    """
    Base Queue model.

    Derive to make your own queues.
    """

    class Meta:
        """
        This is an abstract base class.
        """

        abstract = True

    id = models.BigAutoField(primary_key=True)
    data = JSONField()

    # Use our manager, this is inherited.
    objects = BaseQueueManager()
