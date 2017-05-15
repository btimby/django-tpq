from __future__ import absolute_import

from django.db import models

from main.models import BaseQueue


class FutureQueue(BaseQueue):
    """
    Queue to store futures.
    """

    pass  # objects = FutureManager()


class FutureStat(models.Model):
    """
    Execution statistics.

    This model is updated to reflect futures activity.
    """

    name = models.CharField(max_length=256, unique=True)
    running = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    last_seen = models.DateTimeField(auto_now=True)
    first_seen = models.DateTimeField(auto_now=True)

    def update(self, **kwargs):
        """Shortcut to perform SQL UPDATE for instance."""
        FutureStat.objects.filter(pk=self.pk).update(**kwargs)
