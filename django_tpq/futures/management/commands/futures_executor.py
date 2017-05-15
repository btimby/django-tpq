from __future__ import absolute_import

import logging

from django.core.management.base import BaseCommand

from futures.futures import (
    DEFAULT_QUEUE_NAME, Future, get_queue_model
)


LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Execute futures.
    """

    help = 'Daemon to execute futures.'

    def add_arguments(self, parser):
        parser.add_argument('--queue_name', default=DEFAULT_QUEUE_NAME,
                            help='The queue to monitor. default: %s' %
                            DEFAULT_QUEUE_NAME)
        parser.add_argument('--once', action='store_true', default=False,
                            help='Run one, then exit.')
        parser.add_argument('--wait', type=int, default=0,
                            help='Wait time. Useful with --once.')

    def handle(self, *args, **options):
        """
        Dequeue and execute futures.
        """
        Model = get_queue_model(options['queue_name'])
        while True:
            m = Model.objects.dequeue(wait=options['wait'])
            try:
                Future.execute(m)
            except Exception as e:
                LOGGER.exception(e)
            if options['once']:
                break
