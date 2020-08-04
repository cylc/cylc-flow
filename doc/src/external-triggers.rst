.. _External Triggers:

External Triggers
=================

.. warning::

   This is a new capability and its suite configuration
   interface may change somewhat in future releases - see Current
   Limitations below in :ref:`Current Trigger Function Limitations`.

External triggers allow tasks to trigger directly off of external events, which
is often preferable to implementing long-running polling tasks in the workflow.
The triggering mechanism described in this section replaces an older and less
powerful one documented in :ref:`Old-Style External Triggers`.

If you can write a Python function to check the status of an external
condition or event, the suite server program can call it at configurable
intervals until it reports success, at which point dependent tasks can trigger
and data returned by the function will be passed to the job environments of
those tasks. Functions can be written for triggering off of almost anything,
such as delivery of a new dataset, creation of a new entry in a database
table, or appearance of new data availability notifications in a message
broker.

External triggers are visible in suite visualizations as bare graph nodes (just
the trigger names). They are plotted against all dependent tasks, not in a
cycle point specific way like tasks. This is because external triggers may or
may not be cycle point (or even task name) specific - it depends on the
arguments passed to the corresponding trigger functions. For example, if an
external trigger does not depend on task name or cycle point it will only be
called once - albeit repeatedly until satisfied - for the entire suite run,
after which the function result will be remembered for all dependent tasks
throughout the suite run.

Several built-in external trigger functions are located in
``<cylc-dir>/lib/cylc/xtriggers/``:

- clock triggers - see :ref:`Built-in Clock Triggers`
- inter-suite triggers - see :ref:`Built-in Suite State Triggers`

Trigger functions are normal Python functions, with certain constraints as
described below in:

- custom trigger functions - see :ref:`Custom Trigger Functions`


.. _Built-in Clock Triggers:

Built-in Clock Triggers
-----------------------

These are more transparent (exposed in the graph) and efficient (shared among
dependent tasks) than the older clock triggers described
in :ref:`ClockTriggerTasks`. (However we don't recommend wholesale conversion
to the new method yet, until its interface has stabilized -
see :ref:`Current Trigger Function Limitations`.)

Clock triggers, unlike other trigger functions, are executed synchronously in
the main process. The clock trigger function signature looks like this:

.. code-block:: python

   wall_clock(offset=None)

The ``offset`` argument is a date-time duration (``PT1H`` is 1
hour) relative to the dependent task's cycle point (automatically passed to the
function via a second argument not shown above).

In the following suite, task ``foo`` has a daily cycle point sequence,
and each task instance can trigger once the wall clock time has passed its
cycle point value by one hour:

.. code-block:: cylc

   [scheduling]
       initial cycle point = 2018-01-01
       [[xtriggers]]
           clock_1 = wall_clock(offset=PT1H):PT10S
       [[dependencies]]
           [[[P1D]]]
               graph = "@clock_1 => foo"
   [runtime]
       [[foo]]
           script = run-foo.sh

Notice that the short label ``clock_1`` is used to represent the
trigger function in the graph. The function call interval, which determines how
often the suite server program checks the clock, is optional.  Here it is
``PT10S`` (i.e. 10 seconds, which is also the default value).

Argument keywords can be omitted if called in the right order, so the
``clock_1`` trigger can also be declared like this:

.. code-block:: cylc

   [[xtriggers]]
       clock_1 = wall_clock(PT1H)

A zero-offset clock trigger does not need to be declared under
the ``[xtriggers]`` section:

.. code-block:: cylc

   [scheduling]
       initial cycle point = 2018-01-01
       [[dependencies]]
           [[[P1D]]]
               # zero-offset clock trigger:
               graph = "@wall_clock => foo"
   [runtime]
       [[foo]]
           script = run-foo.sh

However, when xtriggers are declared the name used must contain only
the letters ``a`` to ``z`` in upper or lower case and underscores.


.. _Built-in Suite State Triggers:

Built-in Suite State Triggers
-----------------------------

These can be used instead of the older suite state polling tasks described
in :ref:`SuiteStatePolling` for inter-suite triggering - i.e. to trigger local
tasks off of remote task statuses or messages in other suites. (However we
don't recommend wholesale conversion to the new method yet, until its
interface has stabilized - see :ref:`Current Trigger Function Limitations`.)

The suite state trigger function signature looks like this:

.. code-block:: python

   suite_state(suite, task, point, offset=None, status='succeeded',
               message=None, cylc_run_dir=None, debug=False)

The first three arguments are compulsory; they single out the target suite name
(``suite``) task name (``task``) and cycle point
(``point``). The function arguments mirror the arguments and options of
the ``cylc suite-state`` command - see
``cylc suite-state --help`` for documentation.

As a simple example, consider the suites in
``<cylc-dir>/etc/dev-suites/xtrigger/suite_state/``. The "upstream"
suite (which we want to trigger off of) looks like this:

.. literalinclude:: ../../etc/dev-suites/xtrigger/suite_state/upstream/suite.rc
   :language: cylc

It must be registered and run under the name *up*, as referenced in the
"downstream" suite that depends on it:

.. literalinclude:: ../../etc/dev-suites/xtrigger/suite_state/downstream/suite.rc
   :language: cylc

Try starting the downstream suite first, then the upstream, and
watch what happens.
In each cycle point the ``@upstream`` trigger in the downstream suite
waits on the task ``foo`` (with the same cycle point) in the upstream
suite to emit the *data ready* message.

Some important points to note about this:

- the function call interval, which determines how often the suite
  server program checks the clock, is optional. Here it is
  ``PT10S`` (i.e. 10 seconds, which is also the default value).
- the ``suite_state`` trigger function, like the
  ``cylc suite-state`` command, must have read-access to the upstream
  suite's public database.
- the cycle point argument is supplied by a string template
  ``%(point)s``. The string templates available to trigger function
  arguments are described in :ref:`Custom Trigger Functions`).

The return value of the ``suite_state`` trigger function looks like
this:

.. code-block:: python

   results = {
       'suite': suite,
       'task': task,
       'point': point,
       'offset': offset,
       'status': status,
       'message': message,
       'cylc_run_dir': cylc_run_dir
   }
   return (satisfied, results)

The ``satisified`` variable is boolean (value True or False, depending
on whether or not the trigger condition was found to be satisfied). The
``results`` dictionary contains the names and values of all of the
target suite state parameters. Each item in it gets qualified with the
unique trigger label ("upstream" here) and passed to the environment of
dependent task jobs (the members of the ``FAM`` family in this case).
To see this, take a look at the job script for one of the downstream tasks:

.. code-block:: bash

   % cylc cat-log -f j dn f2.2011
   ...
   cylc__job__inst__user_env() {
       # TASK RUNTIME ENVIRONMENT:
       export upstream_suite upstream_cylc_run_dir upstream_offset \
         upstream_message upstream_status upstream_point upstream_task
       upstream_suite="up"
       upstream_cylc_run_dir="/home/vagrant/cylc-run"
       upstream_offset="None"
       upstream_message="data ready"
       upstream_status="succeeded"
       upstream_point="2011"
       upstream_task="foo"}
   ...

.. note::

   The task has to know the name (label) of the external trigger that it
   depends on - "upstream" in this case - in order to use this information.
   However the name could be given to the task environment in the suite
   configuration.


.. _Custom Trigger Functions:

Custom Trigger Functions
------------------------

Trigger functions are just normal Python functions, with a few special
properties:

- they must:

  - be defined in a module with the same name as the function;
  - be compatible with the same Python version that runs the Cylc workflow
    server program (see :ref:`Requirements` for the latest version
    specification).

- they can be located in:

  - ``<cylc-dir>/lib/cylc/xtriggers/``;
  - ``<suite-dir>/lib/python/``;
  - or anywhere in your Python library path.

- they can take arbitrary positional and keyword arguments
- suite and task identity, and cycle point, can be passed to trigger
  functions by using string templates in function arguments (see below)
- integer, float, boolean, and string arguments will be recognized and
  passed to the function as such
- if a trigger function depends on files or directories (for example)
  that might not exist when the function is first called, just return
  unsatisified until everything required does exist.

.. note::

   Trigger functions cannot store data Pythonically between invocations
   because each call is executed in an independent process in the process
   pool. If necessary the filesystem can be used for this purpose.

The following string templates are available for use, if the trigger function
needs any of this information, in function arguments in the suite configuration:

- ``%(name)s`` - name of the dependent task
- ``%(id)s`` - identity of the dependent task (name.cycle-point)
- ``%(point)s`` - cycle point of the dependent task
- ``%(debug)s`` - suite debug mode

and less commonly needed:

- ``%(user_name)s`` - suite owner's user name
- ``%(suite_name)s`` - registered suite name
- ``%(suite_run_dir)s`` - suite run directory
- ``%(suite_share_dir)s`` - suite share directory

If you need to pass a string template into an xtrigger function as a string
literal - i.e. to be used as a template inside the function - escape it with
``%`` to avoid detection by the Cylc xtrigger parser: ``%%(cat)s``.

Function return values should be as follows:

- if the trigger condition is *not satisfied*:

  - return ``(False, {})``

- if the trigger condition is *satisfied*:

  - return ``(True, results)``

where ``results`` is an arbitrary dictionary of information to be passed to
dependent tasks, which in terms of format must:

- be *flat* (non-nested);
- contain *only* keys which are
  `valid <http://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap08.html>`_ as environment variable names.

See :ref:`Built-in Suite State Triggers` for an example of one such
``results`` dictionary and how it gets processed by the suite.

The suite server program manages trigger functions as follows:

- they are called asynchronously in the process pool
  - (except for clock triggers, which are called from the main process)
- they are called repeatedly on a configurable interval, until satisified
  - the call interval defaults to ``PT10S`` (10 seconds)
  - repeat calls are not made until the previous call has returned
- they are subject to the normal process pool command time out - if they
  take too long to return, the process will be killed
- they are shared for efficiency: a single call will be made for all
  triggers that share the same function signature - i.e.\ the same function
  name and arguments
- their return status and results are stored in the suite DB and persist across
  suite restarts
- their stdout, if any, is redirected to stderr and will be visible in
  the suite log in debug mode (stdout is needed to communicate return values
  from the sub-process in which the function executes)


Toy Examples
^^^^^^^^^^^^

A couple of toy examples in ``<cylc-dir>/lib/cylc/xtriggers/`` may
be a useful aid to understanding trigger functions and how they work.


echo
""""

The ``echo`` function is a trivial one that takes any number of
positional and keyword arguments (from the suite configuration) and simply
prints them to stdout, and then returns False (i.e. trigger condition not
satisfied). Here it is in its entirety.

.. code-block:: python

   def echo(*args, **kwargs):
       print "echo: ARGS:", args
       print "echo: KWARGS:", kwargs
       return (False, {})

Here's an example echo trigger suite:

.. code-block:: cylc

   [scheduling]
       initial cycle point = now
       [[xtriggers]]
           echo_1 = echo(hello, 99, qux=True, point=%(point)s, foo=10)
       [[dependencies]]
           [[[PT1H]]]
               graph = "@echo_1 => foo"
   [runtime]
       [[foo]]
           script = exit 1

To see the result, run this suite in debug mode and take a look at the
suite log (or run ``cylc run --debug --no-detach <suite>`` and watch
your terminal).


xrandom
"""""""

The ``xrandom`` function sleeps for a configurable amount of time
(useful for testing the effect of a long-running trigger function - which
should be avoided) and has a configurable random chance of success. The
function signature is:

.. code-block:: python

   xrandom(percent, secs=0, _=None, debug=False)

The ``percent`` argument sets the odds of success in any given call;
``secs`` is the number of seconds to sleep before returning; and the
``_`` argument (underscore is a conventional name for a variable
that is not used, in Python) is provided to allow specialization of the trigger
to (for example) task name, task ID, or cycle point (just use the appropriate
string templates in the suite configuration for this).

An example xrandom trigger suite is
``<cylc-dir>/etc/dev-suites/xtriggers/xrandom/``.


.. _Current Trigger Function Limitations:

Current Limitations
-------------------

The following issues may be addressed in future Cylc releases:

- trigger labels cannot currently be used in conditional (OR) expressions
  in the graph; attempts to do so will fail validation.
- aside from the predefined zero-offset ``wall_clock`` trigger, all
  unique trigger function calls must be declared *with all of
  their arguments* under the ``[scheduling][xtriggers]`` section, and
  referred to by label alone in the graph. It would be convenient (and less
  verbose, although no more functional) if we could just declare a label
  against the *common* arguments, and give remaining arguments (such as
  different wall clock offsets in clock triggers) as needed in the graph.
- we may move away from the string templating method for providing suite
  and task attributes to trigger function arguments.


Filesystem Events?
------------------

Cylc does not have built-in support for triggering off of filesystem events
such as ``inotify`` on Linux. There is no cross-platform standard for
this, and in any case filesystem events are not very useful in HPC cluster
environments where events can only be detected at the specific node on which
they were generated.


Continuous Event Watchers?
--------------------------

For some applications a persistent process that continually monitors the
external world is better than discrete periodic checking. This would be more
difficult to support as a plugin mechanism in Cylc, but we may decide to do it
in the future. In the meantime, consider implementing a small daemon process as
the watcher (e.g. to watch continuously for filesystem events) and have your
Cylc trigger functions interact with it.


.. _Old-Style External Triggers:

Old-Style External Triggers (Deprecated)
----------------------------------------

.. note::

   This mechanism is now technically deprecated by the newer external
   trigger functions (:ref:`External Triggers`). (However we don't recommend
   wholesale conversion to the new method yet, until its interface has
   stabilized - see :ref:`Current Trigger Function Limitations`.)

These old-style external triggers are hidden task prerequisites that must be
satisfied by using the ``cylc ext-trigger`` client command to send an
associated pre-defined event message to the suite along with an ID string that
distinguishes one instance of the event from another (the name of the target
task and its current cycle point are not required). The event ID is just an
arbitrary string to Cylc, but it can be used to identify something associated
with the event to the suite - such as the filename of a new
externally-generated dataset. When the suite server program receives the event
notification it will trigger the next instance of any task waiting on that
trigger (whatever its cycle point) and then broadcast
(see :ref:`cylc-broadcast`) the event ID to the cycle point of the triggered
task as ``$CYLC_EXT_TRIGGER_ID``. Downstream tasks with the same cycle
point therefore know the new event ID too and can use it, if they need to, to
identify the same new dataset. In this way a whole workflow can be associated
with each new dataset, and multiple datasets can be processed in parallel if
they happen to arrive in quick succession.

An externally-triggered task must register the event it waits on in the suite
scheduling section:

.. code-block:: cylc

   # suite "sat-proc"
   [scheduling]
       cycling mode = integer
       initial cycle point = 1
       [[special tasks]]
           external-trigger = get-data("new sat X data avail")
       [[dependencies]]
           [[[P1]]]
               graph = get-data => conv-data => products

Then, each time a new dataset arrives the external detection system should
notify the suite like this:

.. code-block:: bash

   $ cylc ext-trigger sat-proc "new sat X data avail" passX12334a

where "sat-proc" is the suite name and "passX12334a" is the ID string for
the new event. The suite passphrase must be installed on triggering account.

.. note::

   Only one task in a suite can trigger off a particular external message.
   Other tasks can trigger off the externally triggered task as required,
   of course.

``<cylc-dir>/etc/examples/satellite/ext-triggers/suite.rc`` is a working
example of a simulated satellite processing suite.

External triggers are not normally needed in date-time cycling suites driven
by real time data that comes in at regular intervals. In these cases a data
retrieval task can be clock-triggered (and have appropriate retry intervals) to
submit at the expected data arrival time, so little time is wasted in polling.
However, if the arrival time of the cycle-point-specific data is highly
variable, external triggering may be used with the cycle point embedded in the
message:

.. code-block:: cylc

   # suite "data-proc"
   [scheduling]
       initial cycle point = 20150125T00
       final cycle point   = 20150126T00
       [[special tasks]]
           external-trigger = get-data("data arrived for $CYLC_TASK_CYCLE_POINT")
       [[dependencies]]
           [[[T00]]]
               graph = init-process => get-data => post-process

Once the variable-length waiting is finished, an external detection system
should notify the suite like this:

.. code-block:: bash

   $ cylc ext-trigger data-proc "data arrived for 20150126T00" passX12334a

where "data-proc" is the suite name, the cycle point has replaced the
variable in the trigger string, and "passX12334a" is the ID string for
the new event. The suite passphrase must be installed on the triggering
account. In this case, the event will trigger for the second cycle point but
not the first because of the cycle-point matching.
