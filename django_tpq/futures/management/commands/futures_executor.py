from __future__ import absolute_import

import logging
import signal
import time

from multiprocessing import Process

from django.conf import settings
from django.core.management.base import BaseCommand
from django import db

from futures.futures import (
    Future, get_queue_model
)


LOGGER = logging.getLogger(__name__)


def close_connections():
    """
    Close and delete Django DB connections.
    """
    for c in db.connections:
        db.connections[c].close()
        del db.connections[c]


def executor(Model, limit=-1, wait=0, **options):
    running = True

    def _signal(signum, frame):
        LOGGER.info('Received signal')
        running = False

    # Exit gracefully (after current work) on TERM signal.
    signal.signal(signal.SIGTERM, _signal)

    while running:

        try:
            Future.execute(Model.objects.dequeue(wait=wait))
        except Exception as e:
            LOGGER.exception(e)

        if limit > 0:
            limit -= 1
        if limit == 0:
            break

    LOGGER.info('Graceful exit')


class Command(BaseCommand):
    """
    Execute futures.
    """

    help = 'Daemon to execute futures.'

    def add_arguments(self, parser):
        parser.add_argument('--queue_name',
                            default=settings.FUTURES_QUEUE_NAME,
                            help='The queue to monitor. default: %s' %
                            settings.FUTURES_QUEUE_NAME)
        parser.add_argument('--wait', type=int, default=0,
                            help='Wait time. Useful with --once.')
        parser.add_argument('--workers', type=int, default=1,
                            help='Number of concurrent executors.')
        parser.add_argument('--limit', type=int, default=0,
                            help='Limit number of executions per worker')
        parser.add_argument('--restart', action='store_true', default=True,
                            help='Restart dead processes.')

    def handle(self, *args, **options):
        """
        Dequeue and execute futures.
        """
        Model = get_queue_model(options['queue_name'])

        def _create_worker(**kwargs):
            p = Process(target=executor, args=(Model,), kwargs=kwargs)
            p.start()
            return p

        # Ensure database connections are not inherited.
        close_connections()

        pool = []
        for i in range(options['workers']):
            pool.append(_create_worker(**options))

        try:
            while True:

                # Check if any workers have died.
                for i, p in enumerate(pool):
                    if not p.is_alive():
                        LOGGER.info('Process %s died', p.pid)
                        if options['restart']:
                            LOGGER.info('Restarting worker')
                            pool[i] = _create_worker(**options)

                # Exit if not restarting and no live workers.
                if not options['restart']:
                    if not any([p.is_alive() for p in pool]):
                        break

                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

        for p in pool:
            p.terminate()
            p.join()
