Trivial Postgres Queue for Django
=================================

This is a Django application that integrates tpq. This applications provides
basic message queue capabilities as well as a high-level futures implementation.

Message Queue
-------------

To implement a message queue, you must first create a model derived from the
abstract `BaseQueue` model. Once done, use the `queuemigrations` management
command to create the migrations for your model. The standard `makemigrations`
is not capable of producing the custom SQL needed for triggers and supporting
database objects.

```python
from django_tpq.main.models import BaseQueue

class MyQueue(BaseQueue):
    pass
```

```bash
$ python manage.py queuemigrations
$ python manage.py migrate
```

Now you can use the model and it's custom manager as the interface to your
queue.

```python
from myapp.models import MyQueue

MyQueue.objects.enqueue({'field': 'value'})
message = MyQueue.objects.dequeue()
```

Futures
-------

Using the above as a foundation, a simple Futures implementation is provided.
First you must register any function you wish to call asynchronously as a task.
Then call that task. You can optionally wait or poll for the results.

```python
import time

from django_tpq.futures.decorators import task


@task
def long_running_function(*args):
    time.sleep(100)

f = long_running_function.delay('argument_1')

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

f = long_running_function.delay('argument_1')

try:
    r = f.result(wait=0)
except Exception:
    # Exceptions are re-raised.
    LOGGER.exception('Future failed', exc_info)

print(r)
```

Function calls are dispatched via a message queue. Arguments are pickled, so you
can send any picklable Python objects. Results are delivered via your configured
cache. By default the `default` cache is used, but you can use the
`TPQ_RESULT_CACHE` setting to provide an alternate name for the Django cache you
want to be used for results. Results have a TTL of 60 minutes by default but you
can adjust this using the `TPQ_RESULT_TTL` setting.

Tasks are executed by a daemon started using a Django management command.

```bash
$ python manage.py executor --help

 --foreground, -f - run in foreground
 --threads, -t - number of concurrent executor threads
```

Some task statistics are also stored in your Postgres database for reporting
purposes.

```python
from django_tpq.futures.models import Task

Task.objects.all()
```

The task model has the following fields.

 - name - The python module.function of the task.
 - running - The number of currently executing tasks of this type.
 - total - The total number of executed tasks of this type.
 - failures - The number of tasks resulting in an exception.
 - last_seen - The timestamp of the most recent execution of the task.
 - first_seen - The timestamp of the least recent execution of the task.

Being a model, you can use the Django ORM to report on these fields any way you
see fit.