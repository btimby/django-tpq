from __future__ import absolute_import

from django.db import models


class Futures(BaseQueue):
    """
    Queue to store futures.
    """

    pass


class FuturesStats(models.Model):
    """
    Execution statistics.

    This model is updated to reflect futures activity.
    """

    pass
