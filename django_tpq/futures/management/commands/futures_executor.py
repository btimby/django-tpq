from __future__ import absolute_import

import logging
import multiprocessing
import signal
import time
import threading

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


def executor_t(Model, stopping, limit=-1, wait=0, **options):
    """
    Executor thread.

    Entry point for worker threads. Will iteratively dequeue and process
    futures until signaled to stop or until limit is reached.
    """
    while not stopping.is_set():

        try:
            Future.execute(Model.objects.dequeue(wait=wait))
        except Exception as e:
            LOGGER.exception(e)

        if limit > 0:
            limit -= 1

        if limit == 0:
            LOGGER.info('Processing limit reached')
            break

    LOGGER.info('Thread exiting')


def executor_p(Model, limit=-1, wait=0, threads=1, **options):
    """
    Executor process.

    Entry point for worker processes. Starts the specified number of threads.
    Handles SIGTERM by asking them to exit gracefully. Then waits for them to
    exit. Each thread will process `limit` tasks before exiting itself.
    """
    stopping = threading.Event()

    def _signal(signum, frame):
        LOGGER.info('Received signal')
        stopping.set()

    # Exit gracefully (after current work) on TERM signal.
    signal.signal(signal.SIGTERM, _signal)

    def _thread(**kwargs):
        t = threading.Thread(target=executor_t, args=(Model, stopping),
                             kwargs=kwargs)
        t.start()
        return t

    pool = []
    LOGGER.info('Starting %s threads', threads)
    for i in range(threads):
        pool.append(_thread(limit=limit, wait=wait, **options))

    for t in pool:
        t.join()
        LOGGER.info('Thread %s died', t.ident)

    LOGGER.info('Process exiting')


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
        parser.add_argument('--processes', type=int, default=1,
                            help='Number of concurrent executor processes.')
        parser.add_argument('--threads', type=int, default=1,
                            help='Number of concurrent executor threads per '
                                 'process.')
        parser.add_argument('--limit', type=int, default=0,
                            help='Limit number of executions per thread '
                                 'default: 0 (no limit).')
        parser.add_argument('--restart', action='store_true', default=True,
                            help='Restart dead processes.')

    def handle(self, *args, **options):
        """
        Dequeue and execute futures.
        """
        Model = get_queue_model(options['queue_name'])

        def _process(**kwargs):
            p = multiprocessing.Process(target=executor_p, args=(Model,),
                                        kwargs=kwargs)
            p.start()
            return p

        # Ensure database connections are not inherited.
        close_connections()

        pool = []
        LOGGER.info('Starting %s processes', options['workers'])
        for i in range(options['workers']):
            pool.append(_process(**options))

        try:
            while True:

                # Check if any workers have died.
                for i, p in enumerate(pool):
                    if not p.is_alive():
                        LOGGER.info('Process %s died', p.pid)
                        del p
                        if options['restart']:
                            p = pool[i] = _process(**options)
                            LOGGER.info('Restarted process %s', p.pid)

                # Exit if not restarting and no live workers.
                if not options['restart']:
                    if not any([p.is_alive() for p in pool]):
                        LOGGER.info('All processes dead, terminating executor')
                        break

                time.sleep(0.5)
        except KeyboardInterrupt:
            LOGGER.info('Received KeyboardInterrupt')

        for p in pool:
            LOGGER.info('Requesting %s shutdown', p.pid)
            p.terminate()
            p.join()

        LOGGER.info('All workers terminated')
