.. image:: https://travis-ci.org/btimby/django-tpq.svg?branch=master
   :alt: Travis CI Status
   :target: https://travis-ci.org/btimby/django-tpq

.. image:: https://coveralls.io/repos/github/btimby/django-tpq/badge.svg?branch=master
    :target: https://coveralls.io/github/btimby/django-tpq?branch=master
    :alt: Code Coverage

.. image:: https://badge.fury.io/py/django-tpq.svg
    :target: https://badge.fury.io/py/django-tpq

Trivial Postgres Queue for Django
=================================

This is a Django application that integrates
`tpq <https://github.com/btimby/tpq/>`_. This application provides basic
message queue capabilities as well as a high-level futures implementation.

Message Queue
-------------

To implement a message queue, you must first create a model derived from the
abstract ``BaseQueue`` model. Once done, create a migration for that model, then
edit the migration to add some additional database objects (tpq does this for
you, but you must call it from the migration). Then migrate and use your queue.

.. code:: python

    from django_tpq.main.models import BaseQueue

    class MyQueue(BaseQueue):
        pass
    ```

::

    $ python manage.py makemigrations

Now edit the migration and add the RunPython step as is done with the futures
'initial migration <django_tpq/futures/migrations/0001_initial.py>`_. You will
also need to customize the model name in the ``forward`` function.

::

    $ python manage.py migrate


.. code:: python

    from myapp.models import MyQueue

    MyQueue.objects.enqueue({'field': 'value'})
    message = MyQueue.objects.dequeue()

Futures
-------

Using the above as a foundation, a simple Futures implementation is provided.
First you must register any function you wish to call asynchronously as a task.
Then call that task. You can optionally wait or poll for the results.

.. code:: python
    import time

    from django_tpq.futures.decorators import future


    @task()
    def long_running_function(*args):
        time.sleep(100)

    # You can execute the task without waiting for a result. This returns
    # immediately and your task runs within another process (fire and forget).
    long_running_function.async('argument_1')

    # Or you can poll for the results (or check after you do some other work).
    f = long_running_function.async('argument_1')

    while True:
        if f.is_done():
            try:
                r = f.result()
            except Exception:
                # Exceptions are re-raised.
                LOGGER.exception('Future failed', exc_info)
            else:
                break
        time.sleep(10)

    print(r)

    # Or optionally, you can block waiting for the result.
    f = long_running_function.call('argument_1')

    try:
        r = f.result(wait=0)
    except Exception:
        # Exceptions are re-raised.
        LOGGER.exception('Future failed', exc_info)

    print(r)

Function calls are dispatched via a message queue. Arguments are pickled, so you
can send any picklable Python objects. Results are delivered via your configured
cache. By default the ``default`` cache is used, but you can use the
``TPQ_RESULT_CACHE`` setting to provide an alternate name for the Django cache
you want to be used for results. Results have a TTL of 60 minutes by default
but you can adjust this using the ``TPQ_RESULT_TTL`` setting.

Tasks are executed by a daemon started using a Django management command.

::

    $ python manage.py executor --help

     --foreground, -f - run in foreground
     --threads, -t - number of concurrent executor threads

Some task statistics are also stored in your Postgres database for reporting
purposes.

.. code:: python

    from django_tpq.futures.models import FutureStat

    FutureStat.objects.all()

The task model has the following fields.

 - name - The python module.function of the task.
 - running - The number of currently executing tasks of this type.
 - total - The total number of executed tasks of this type.
 - failed - The number of tasks resulting in an exception.
 - last_seen - The timestamp of the most recent execution of the task.
 - first_seen - The timestamp of the least recent execution of the task.

Being a model, you can use the Django ORM to report on these fields any way you
see fit.