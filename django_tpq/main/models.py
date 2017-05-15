from django.db import models
from django.db import connection
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ObjectDoesNotExist

import tpq


class BaseQueueManager(models.Manager):
    def enqueue(self, d):
        assert isinstance(d, dict), 'Must enqueue a dictionary'
        tpq.put(self.model._meta.db_table, d, conn=connection)

    def dequeue(self, wait=-1):
        try:
            return tpq.get(self.model._meta.db_table, wait=wait,
                           conn=connection)
        except tpq.QueueEmpty:
            raise ObjectDoesNotExist


class BaseQueue(models.Model):
    """
    Base Queue model.
    """

    class Meta:
        abstract = True

    id = models.BigAutoField(primary_key=True)
    data = JSONField()

    objects = BaseQueueManager()
