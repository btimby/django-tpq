from django.db import models
from django.contrib.postgres.fields import JSONField


class BaseQueue(models.Model):
    """
    Base Queue model.
    """

    class Meta:
        abstract = True

    id = models.BigAutoField()
    data = JSONField()
