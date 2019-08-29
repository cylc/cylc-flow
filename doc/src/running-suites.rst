.. _RunningSuites:

Running Suites
==============

This chapter currently features a diverse collection of topics related
to running suites. Please also see :ref:`Tutorial` and
:ref:`CommandReference`, and experiment with plenty of examples.


.. _SuiteStartUp:

Suite Start-Up
--------------

There are three ways to start a suite running: *cold start* and *warm start*,
which start from scratch; and *restart*, which starts from a prior
suite state checkpoint. The only difference between cold starts and warm starts
is that warm starts start from a point beyond the suite initial cycle point.

Once a suite is up and running it is typically a restart that is needed most
often (but see also ``cylc reload``). *Be aware that cold and warm
starts wipe out prior suite state, so you can't go back to a restart if you
decide you made a mistake.*


.. _Cold Start:

Cold Start
^^^^^^^^^^

A cold start is the primary way to start a suite run from scratch:

.. code-block:: bash

   $ cylc run SUITE [INITIAL_CYCLE_POINT]

The initial cycle point may be specified on the command line or in the suite.rc
file. The scheduler starts by loading the first instance of each task at the
suite initial cycle point, or at the next valid point for the task.


.. _Warm Start:

Warm Start
^^^^^^^^^^

A warm start runs a suite from scratch like a cold start, but from the
beginning of a given cycle point that is beyond the suite initial cycle point.
This is generally inferior to a *restart* (which loads a previously
recorded suite state - see :ref:`RestartingSuites`) because it may result in
some tasks rerunning. However, a warm start may be required if a restart is not
possible, e.g. because the suite run database was accidentally deleted. The
warm start cycle point must be given on the command line:

.. code-block:: bash

   $ cylc run --warm SUITE [START_CYCLE_POINT]

The original suite initial cycle point is preserved, but all tasks and
dependencies before the given warm start cycle point are ignored.

The scheduler starts by loading a first instance of each task at the warm
start cycle point, or at the next valid point for the task.
``R1``-type tasks behave exactly the same as other tasks - if their
cycle point is at or later than the given start cycle point, they will run; if
not, they will be ignored.


.. _RestartingSuites:

Restart and Suite State Checkpoints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

At restart (see ``cylc restart --help``) a suite server program
initializes its task pool from a previously recorded checkpoint state. By
default the latest automatic checkpoint - which is updated with every task
state change - is loaded so that the suite can carry on exactly as it was just
before being shut down or killed.

.. code-block:: bash

   $ cylc restart SUITE

Tasks recorded in the "submitted" or "running" states are automatically polled
(see :ref:`Task Job Polling`) at start-up to determine what happened to
them while the suite was down.


Restart From Latest Checkpoint
""""""""""""""""""""""""""""""

To restart from the latest checkpoint simply invoke the ``cylc restart``
command with the suite name (or select "restart" in the GUI suite start dialog
window):

.. code-block:: bash

   $ cylc restart SUITE


Restart From Another Checkpoint
"""""""""""""""""""""""""""""""

Suite server programs automatically update the "latest" checkpoint every time
a task changes state, and at every suite restart, but you can also take
checkpoints at other times. To tell a suite server program to checkpoint its
current state:

.. code-block:: bash

   $ cylc checkpoint SUITE-NAME CHECKPOINT-NAME

The 2nd argument is a name to identify the checkpoint later with:

.. code-block:: bash

   $ cylc ls-checkpoints SUITE-NAME

For example, with checkpoints named "bob", "alice", and "breakfast":

.. code-block:: bash

   $ cylc ls-checkpoints SUITE-NAME
   #######################################################################
   # CHECKPOINT ID (ID|TIME|EVENT)
   1|2017-11-01T15:48:34+13|bob
   2|2017-11-01T15:48:47+13|alice
   3|2017-11-01T15:49:00+13|breakfast
   ...
   0|2017-11-01T17:29:19+13|latest

To see the actual task state content of a given checkpoint ID (if you need to),
for the moment you have to interrogate the suite DB, e.g.:

.. code-block:: bash

   $ sqlite3 ~/cylc-run/SUITE-NAME/log/db \
       'select * from task_pool_checkpoints where id == 3;'
   3|2012|model|1|running|
   3|2013|pre|0|waiting|
   3|2013|post|0|waiting|
   3|2013|model|0|waiting|
   3|2013|upload|0|waiting|

.. note::

   A checkpoint captures the instantaneous state of every task in the
   suite, including any tasks that are currently active, so you may want
   to be careful where you do it. Tasks recorded as active are polled
   automatically on restart to determine what happened to them.

The checkpoint ID 0 (zero) is always used for latest state of the suite, which
is updated continuously as the suite progresses. The checkpoint IDs of earlier
states are positive integers starting from 1, incremented each time a new
checkpoint is stored. Currently suites automatically store checkpoints before
and after reloads, and on restarts (using the latest checkpoints before the
restarts).

Once you have identified the right checkpoint, restart the suite like this:

.. code-block:: bash

   $ cylc restart --checkpoint=CHECKPOINT-ID SUITE

or enter the checkpoint ID in the space provided in the GUI restart window.


Checkpointing With A Task
"""""""""""""""""""""""""

Checkpoints can be generated automatically at particular points in the
workflow by coding tasks that run the ``cylc checkpoint`` command:

.. code-block:: cylc

   [scheduling]
      [[dependencies]]
         [[[PT6H]]]
             graph = "pre => model => post => checkpointer"
   [runtime]
      # ...
      [[checkpointer]]
         script = """
   wait "${CYLC_TASK_MESSAGE_STARTED_PID}" 2>/dev/null || true
   cylc checkpoint ${CYLC_SUITE_NAME} CP-${CYLC_TASK_CYCLE_POINT}
                  """

.. note::

   We need to "wait" on the "task started" message - which
   is sent in the background to avoid holding tasks up in a network
   outage - to ensure that the checkpointer task is correctly recorded
   as running in the checkpoint (at restart the suite server program will
   poll to determine that that task job finished successfully). Otherwise
   it may be recorded in the waiting state and, if its upstream dependencies
   have already been cleaned up, it will need to be manually reset from waiting
   to succeeded after the restart to avoid stalling the suite.


Behaviour of Tasks on Restart
"""""""""""""""""""""""""""""

All tasks are reloaded in exactly their checkpointed states. Failed tasks are
not automatically resubmitted at restart in case the underlying problem has not
been addressed yet.

Tasks recorded in the submitted or running states are automatically polled on
restart, to see if they are still waiting in a batch queue, still running, or
if they succeeded or failed while the suite was down. The suite state will be
updated automatically according to the poll results.

Existing instances of tasks removed from the suite configuration before restart
are not removed from the task pool automatically, but they will not spawn new
instances. They can be removed manually if necessary,
with~``cylc remove``.

Similarly, instances of new tasks added to the suite configuration before
restart are not inserted into the task pool automatically, because it is
very difficult in general to automatically determine the cycle point of
the first instance. Instead, the first instance of a new task should be
inserted manually at the right cycle point, with ``cylc insert``.


Reloading The Suite Configuration At Runtime
--------------------------------------------

The ``cylc reload`` command tells a suite server program to reload its
suite configuration at run time. This is an alternative to shutting a
suite down and restarting it after making changes.

As for a restart, existing instances of tasks removed from the suite
configuration before reload are not removed from the task pool
automatically, but they will not spawn new instances. They can be removed
manually if necessary, with ``cylc remove``.

Similarly, instances of new tasks added to the suite configuration before
reload are not inserted into the pool automatically. The first instance of each
must be inserted manually at the right cycle point, with ``cylc insert``.


.. _HowTasksGetAccessToCylc:

Task Job Access To Cylc
-----------------------

Task jobs need access to Cylc on the job host, primarily for task messaging,
but also to allow user-defined task scripting to run other Cylc commands.

Cylc should be installed on job hosts as on suite hosts, with different
releases installed side-by-side and invoked via the central Cylc
wrapper according to the value of ``$CYLC_VERSION`` - see
:ref:`InstallCylc`. Task job scripts set ``$CYLC_VERSION`` to the
version of the parent suite server program, so that the right Cylc will
be invoked by jobs on the job host.

Access to the Cylc executable (preferably the central wrapper as just
described) for different job hosts can be configured using site and user
global configuration files (on the suite host). If the environment for running
the Cylc executable is only set up correctly in a login shell for a given host,
you can set ``[hosts][HOST]use login shell = True`` for the relevant
host (this is the default, to cover more sites automatically). If the
environment is already correct without the login shell, but the Cylc executable
is not in ``$PATH``, then ``[hosts][HOST]cylc executable`` can
be used to specify the direct path to the executable.

To customize the environment more generally for Cylc on jobs hosts,
use of ``job-init-env.sh`` is described in
:ref:`Configure Environment on Job Hosts`.


.. _The Suite Contact File:

The Suite Contact File
----------------------

At start-up, suite server programs write a *suite contact file*
``$HOME/cylc-run/SUITE/.service/contact`` that records suite host,
user, port number, process ID, Cylc version, and other information. Client
commands can read this file, if they have access to it, to find the target
suite server program.


.. _Task Job Polling:

Task Job Polling
----------------

At any point after job submission task jobs can be *polled* to check that
their true state conforms to what is currently recorded by the suite server
program.  See ``cylc poll --help`` for how to poll one or more tasks
manually, or right-click poll a task or family in GUI.

Polling may be necessary if, for example, a task job gets killed by the
untrappable SIGKILL signal (e.g. ``kill -9 PID``), or if a network
outage prevents task success or failure messages getting through, or if the
suite server program itself is down when tasks finish execution.

To poll a task job the suite server program interrogates the
batch system, and the ``job.status`` file, on the job host. This
information is enough to determine the final task status even if the
job finished while the suite server program was down or unreachable on
the network.


Routine Polling
^^^^^^^^^^^^^^^

Task jobs are automatically polled at certain times: once on job submission
timeout; several times on exceeding the job execution time limit; and at suite
restart any tasks recorded as active in the suite state checkpoint are polled
to find out what happened to them while the suite was down.

Finally, in necessary routine polling can be configured as a way to track job
status on job hosts that do not allow networking routing back to the suite host
for task messaging by HTTPS or ssh. See :ref:`Polling To Track Job Status`.


.. _TaskComms:

Tracking Task State
-------------------

Cylc supports three ways of tracking task state on job hosts:

- task-to-suite messaging via HTTPS
- task-to-suite messaging via non-interactive ssh to the suite host,
  then local HTTPS
- regular polling by the suite server program

These can be configured per job host in the Cylc global config file - see
:ref:`SiteRCReference`.

If your site prohibits HTTPS and ssh back from job hosts to
suite hosts, before resorting to the polling method you should
consider installing dedicated Cylc servers or
VMs inside the HPC trust zone (where HTTPS and ssh should be allowed).

It is also possible to run Cylc suite server programs on HPC login
nodes, but this is not recommended for load, run duration,
and GUI reasons.

Finally, it has been suggested that *port forwarding* may provide another
solution - but that is beyond the scope of this document.


HTTPS Task Messaging
^^^^^^^^^^^^^^^^^^^^

Task job wrappers automatically invoke ``cylc message`` to report
progress back to the suite server program when they begin executing,
at normal exit (success) and abnormal exit (failure).

By default the messaging occurs via an authenticated, HTTPS connection to the
suite server program. This is the preferred task communications
method - it is efficient and direct.

Suite server programs automatically install suite contact information
and credentials on job hosts.  Users only need to do this manually
for remote access to suites on other hosts, or suites owned by other
users - see :ref:`RemoteControl`.


Ssh Task Messaging
^^^^^^^^^^^^^^^^^^

Cylc can be configured to re-invoke task messaging commands on the
suite host via non-interactive ssh (from job host to suite host).
Then a local HTTPS connection is made to the suite server program.

(User-invoked client commands (aside from the GUI, which requires HTTPS)
can do the same thing with the ``--use-ssh`` command option).

This is less efficient than direct HTTPS messaging, but it may be useful at
sites where the HTTPS ports are blocked but non-interactive ssh is allowed.


.. _Polling To Track Job Status:

Polling to Track Job Status
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Finally, suite server programs can actively poll task jobs at
configurable intervals, via non-interactive ssh to the job host.

Polling is the least efficient task communications method because task state is
updated only at intervals, not when task events actually occur.  However, it
may be needed at sites that do not allow HTTPS or non-interactive ssh from job
host to suite host.

Be careful to avoid spamming task hosts with polling commands. Each poll
opens (and then closes) a new ssh connection.

Polling intervals are configurable under ``[runtime]`` because
they should may depend on the expected execution time. For instance, a
task that typically takes an hour to run might be polled every 10
minutes initially, and then every minute toward the end of its run.
Interval values are used in turn until the last value, which is used
repeatedly until finished:

.. code-block:: cylc

   [runtime]
       [[foo]]
           [[[job]]]
               # poll every minute in the 'submitted' state:
               submission polling intervals = PT1M
               # poll one minute after foo starts running, then every 10
               # minutes for 50 minutes, then every minute until finished:
               execution polling intervals = PT1M, 5*PT10M, PT1M

A list of intervals with optional multipliers can be used for both
submission and execution polling, although a single value is probably
sufficient for submission polling. If these items are not configured
default values from site and user global config will be used for the polling
task communication method; polling is not done by default under the
other task communications methods (but it can still be used if you
like).


Task Communications Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. _The Suite Service Directory:

The Suite Service Directory
---------------------------

At registration time a *suite service directory*,
``$HOME/cylc-run/<SUITE>/.service/``, is created and populated
with a private passphrase file (containing random text), a self-signed
SSL certificate (see :ref:`ConnectionAuthentication`), and a symlink to the
suite source directory.  An existing passphrase file will not be overwritten
if a suite is re-registered.

At run time, the private suite run database is also written to the service
directory, along with a *suite contact file* that records the host,
user, port number, process ID, Cylc version, and other information about the
suite server program. Client commands automatically read daemon targetting
information from the contact file, if they have access to it.


File-Reading Commands
---------------------

Some Cylc commands and GUI actions parse suite configurations or read
other files
from the suite host account, rather than communicate with a suite server
program over the network. In future we plan to have suite server program serve
up these files to clients, but for the moment this functionality requires
read-access to the relevant files on the suite host.

If you are logged into the suite host account, file-reading commands will just
work.


Remote Host, Shared Home Directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are logged into another host with shared home directories (shared
filesystems are common in HPC environments) file-reading commands will just
work because suite files will look "local" on both hosts.


Remote Host, Different Home Directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are logged into another host with no shared home directory, file-reading
commands require non-interactive ssh to the suite host account, and use of the
``--host`` and ``--user`` options to re-invoke the command
on the suite account.


Same Host, Different User Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

(This is essentially the same as *Remote Host, Different Home Directory*.)


.. _ConnectionAuthentication:

Client-Server Interaction
-------------------------

Cylc server programs listen on dedicated network ports for
HTTPS communications from Cylc clients (task jobs, and user-invoked commands
and GUIs).

Use ``cylc scan`` to see which suites are listening on which ports on
scanned hosts (this lists your own suites by default, but it can show others
too - see ``cylc scan --help``).

Cylc supports two kinds of access to suite server programs:

- *public* (non-authenticated) - the amount of information
  revealed is configurable, see :ref:`PublicAccess`
- *control* (authenticated) - full control, suite passphrase
  required, see :ref:`passphrases`


.. _PublicAccess:

Public Access - No Auth Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Without a suite passphrase the amount of information revealed by a suite
server program is determined by the public access privilege level set in global
site/user config (:ref:`GlobalAuth`) and optionally overidden in suites
(:ref:`SuiteAuth`):

- *identity* - only suite and owner names revealed
- *description* - identity plus suite title and description
- *state-totals* - identity, description, and task state totals
- *full-read* - full read-only access for monitor and GUI
- *shutdown* - full read access plus shutdown, but no other control.

The default public access level is *state-totals*.

The ``cylc scan`` command and the ``cylc gscan`` GUI can print
descriptions and task state totals in addition to basic suite identity, if the
that information is revealed publicly.


.. _passphrases:

Full Control - With Auth Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Suite auth files (passphrase and SSL certificate) give full control. They are
loaded from the suite service directory by the suite server program at
start-up, and used to authenticate subsequent client connections. Passphrases
are used in a secure encrypted challenge-response scheme, never sent in plain
text over the network.

If two users need access to the same suite server program, they must both
possess the passphrase file for that suite. Fine-grained access to a single
suite server program via distinct user accounts is not currently supported.

Suite server programs automatically install their auth and contact files to job
hosts via ssh, to enable task jobs to connect back to the suite server program
for task messaging.

Client programs invoked by the suite owner automatically load the passphrase,
SSL certificate, and contact file too, for automatic connection to suites.

*Manual installation of suite auth files is only needed for remote control,
if you do not have a shared filesystem - see below.*


.. _GUI-to-Suite Interaction:

GUI-to-Suite Interaction
------------------------

The gcylc GUI is mainly a network client to retrieve and display suite status
information from the suite server program, but it can also invoke file-reading
commands to view and graph the suite configuration and so on. This is entirely
transparent if the GUI is running on the suite host account, but full
functionality for remote suites requires either a shared filesystem, or
(see :ref:`RemoteControl`) auth file installation *and* non-interactive ssh
access to the suite host.  Without the auth files you will not be able
to connect to the suite, and without ssh you will see "permission denied"
errors on attempting file access.


.. _RemoteControl:

Remote Control
--------------

Cylc client programs - command line and GUI - can interact with suite server
programs running on other accounts or hosts. How this works depends on whether
or not you have:

- a *shared filesystem* such that you see the same home directory on
  both hosts.
- *non-interactive ssh* from the client account to the server
  account.

With a shared filesystem, a suite registered on the remote (server) host is
also - in effect - registered on the local (client) host.  In this case you
can invoke client commands without the ``--host`` option; the client
will automatically read the host and port from the contact file in the
suite service directory.

To control suite server programs running under other user accounts or on other
hosts without a shared filesystem, the suite SSL certificate and passphrase
must be installed under your ``$HOME/.cylc/`` directory:

.. code-block:: bash

   $HOME/.cylc/auth/OWNER@HOST/SUITE/
         ssl.cert
         passphrase
         contact  # (optional - see below)

where ``OWNER@HOST`` is the suite host account and ``SUITE``
is the suite name. Client commands should then be invoked with the
``--user`` and ``--host`` options, e.g.:

.. code-block:: bash

   $ cylc gui --user=OWNER --host=HOST SUITE

.. note::

   Remote suite auth files do not need to be installed for read-only
   access - see :ref:`PublicAccess` - via the GUI or monitor.

The suite contact file (see :ref:`The Suite Contact File`) is not needed if
you have read-access to the remote suite run directory via the local
filesystem or non-interactive ssh to the suite host account - client commands
will automatically read it. If you do install the contact file in your auth
directory note that the port number will need to be updated if the suite gets
restarted on a different port. Otherwise use ``cylc scan`` to determine
the suite port number and use the ``--port`` client command option.

.. warning::

   Possession of a suite passphrase gives full control over the
   target suite, including edit run functionality - which lets you run
   arbitrary scripting on job hosts as the suite owner. Further,
   non-interactive ssh gives full access to the target user account, so we
   recommended that this is only used to interact with suites running on
   accounts to which you already have full access.


.. _Scan And Gscan:

Scan And Gscan
--------------

Both ``cylc scan`` and the ``cylc gscan`` GUI can display
suites owned by other users on other hosts, including task state totals if the
public access level permits that (see :ref:`PublicAccess`). Clicking on a
remote suite in ``gscan`` will open a ``cylc gui`` to connect to that
suite. This will give you full control, if you have the suite auth files
installed; or it will display full read only information if the public access
level allows that.


Task States Explained
---------------------

As a suite runs, its task proxies may pass through the following states:

- **waiting** - still waiting for prerequisites (e.g. dependence on
  other tasks, and clock triggers) to be satisfied.
- **held** - will not be submitted to run even if all prerequisites
  are satisfied, until released/un-held.
- **queued** - ready to run (prerequisites satisfied) but
  temporarily held back by an *internal cylc queue*
  (see :ref:`InternalQueues`).
- **ready** - ready to run (prerequisites satisfied) and
  handed to cylc's job submission sub-system.
- **submitted** - submitted to run, but not executing yet
  (could be waiting in an external batch scheduler queue).
- **submit-failed** - job submission failed *or*
  submitted job killed (cancelled) before commencing execution.
- **submit-retrying** - job submission failed, but a submission retry
  was configured. Will only enter the *submit-failed* state if all
  configured submission retries are exhausted.
- **running** - currently executing (a *task started*
  message was received, or the task polled as running).
- **succeeded** - finished executing successfully (a *task
  succeeded* message was received, or the task polled as succeeded).
- **failed** - aborted execution due to some error condition (a
  *task failed* message was received, or the task polled as failed).
- **retrying** - job execution failed, but an execution retry
  was configured. Will only enter the *failed* state if all configured
  execution retries are exhausted.
- **runahead** - will not have prerequisites checked (and so
  automatically held, in effect) until the rest of the suite catches up
  sufficiently.  The amount of runahead allowed is configurable - see
  :ref:`RunaheadLimit`.
- **expired** - will not be submitted to run, due to falling too far
  behind the wall-clock relative to its cycle point -
  see :ref:`ClockExpireTasks`.


What The Suite Control GUI Shows
--------------------------------

The GUI Text-tree and Dot Views display the state of every task proxy present
in the task pool. Once a task has succeeded and Cylc has determined that it can
no longer be needed to satisfy the prerequisites of other tasks, its proxy will
be cleaned up (removed from the pool) and it will disappear from the GUI. To
rerun a task that has disappeared from the pool, you need to re-insert its task
proxy and then re-trigger it.

The Graph View is slightly different: it displays the complete dependency graph
over the range of cycle points currently present in the task pool. This often
includes some greyed-out *base* or *ghost nodes* that are empty - i.e.
there are no corresponding task proxies currently present in the pool. Base
nodes just flesh out the graph structure. Groups of them may be cut out and
replaced by single *scissor nodes* in sections of the graph that are
currently inactive.


Network Connection Timeouts
---------------------------

A connection timeout can be set in site and user global config files
(see :ref:`SiteAndUserConfiguration`) so that messaging commands
cannot hang indefinitely if the suite is not responding (this can be
caused by suspending a suite with Ctrl-Z) thereby preventing the task
from completing. The same can be done on the command line for other
suite-connecting user commands, with the ``--comms-timeout`` option.


.. _RunaheadLimit:

Runahead Limiting
-----------------

Runahead limiting prevents the fastest tasks in a suite from getting too far
ahead of the slowest ones. Newly spawned tasks are released to the task pool
only when they fall below the runahead limit. A low runhead limit can prevent
cylc from interleaving cycles, but it will not stall a suite unless it fails to
extend out past a future trigger (see :ref:`InterCyclePointTriggers`).
A high runahead limit may allow fast tasks that are not constrained by
dependencies or clock-triggers to spawn far ahead of the pack, which could have
performance implications for the suite server program when running very large
suites.  Succeeded and failed tasks are ignored when computing the runahead
limit.

The preferred runahead limiting mechanism restricts the number of consecutive
active cycle points. The default value is three active cycle points;
see :ref:`max active cycle points`. Alternatively the interval between the
slowest and fastest tasks can be specified as hard limit;
see :ref:`runahead limit`.


.. _InternalQueues:

Limiting Activity With Internal Queues
--------------------------------------

Large suites can potentially overwhelm task hosts by submitting too many
tasks at once. You can prevent this with *internal queues*, which
limit the number of tasks that can be active (submitted or running)
at the same time.

Internal queues behave in the first-in-first-out (FIFO) manner, i.e. tasks are
released from a queue in the same order that they were queued.

A queue is defined by a *name*; a *limit*, which is the maximum
number of active tasks allowed for the queue; and a list of *members*,
assigned by task or family name.

Queue configuration is done under the ``[scheduling]`` section of the suite.rc
file (like dependencies, internal queues constrain *when* a task runs).

By default every task is assigned to the *default* queue, which by default
has a zero limit (interpreted by cylc as no limit). To use a single queue for
the whole suite just set the default queue limit:

.. code-block:: cylc

   [scheduling]
       [[ queues]]
           # limit the entire suite to 5 active tasks at once
           [[[default]]]
               limit = 5

To use additional queues just name each one, set their limits, and assign
members:

.. code-block:: cylc

   [scheduling]
       [[ queues]]
           [[[q_foo]]]
               limit = 5
               members = foo, bar, baz

Any tasks not assigned to a particular queue will remain in the default
queue. The *queues* example suite illustrates how queues work by
running two task trees side by side (as seen in the graph GUI) each
limited to 2 and 3 tasks respectively:

.. literalinclude:: ../../etc/examples/queues/suite.rc
   :language: cylc


.. _TaskRetries:

Automatic Task Retry On Failure
-------------------------------

See also :ref:`RefRetries`.

Tasks can be configured with a list of "retry delay" intervals, as
ISO 8601 durations. If the task job fails it will go into the *retrying*
state and resubmit after the next configured delay interval. An example is
shown in the suite listed below under :ref:`EventHandling`.

If a task with configured retries is *killed* (by ``cylc kill`` or
via the GUI) it goes to the *held* state so that the operator can decide
whether to release it and continue the retry sequence or to abort the retry
sequence by manually resetting it to the *failed* state.


.. _EventHandling:

Task Event Handling
-------------------

See also :ref:`SuiteEventHandling` and :ref:`TaskEventHandling`.

Cylc can call nominated event handlers - to do whatever you like - when certain
suite or task events occur. This facilitates centralized alerting and automated
handling of critical events. Event handlers can be used to send a message, call
a pager, or whatever; they can even intervene in the operation of their own
suite using cylc commands.

To send an email, use the built-in setting ``[[[events]]]mail events``
to specify a list of events for which notifications should be sent. (The
name of a registered task output can also be used as an event name in
this case.) E.g. to send an email on (submission) failed and retry:

.. code-block:: cylc

   [runtime]
       [[foo]]
           script = """
               test ${CYLC_TASK_TRY_NUMBER} -eq 3
               cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" 'oopsy daisy'
           """
           [[[events]]]
               mail events = submission failed, submission retry, failed, retry, oops
           [[[job]]]
               execution retry delays = PT0S, PT30S
           [[[outputs]]]
               oops = oopsy daisy

By default, the emails will be sent to the current user with:

- ``to:`` set as ``$USER``
- ``from:`` set as ``notifications@$(hostname)``
- SMTP server at ``localhost:25``

These can be configured using the settings:

- ``[[[events]]]mail to`` (list of email addresses),
- ``[[[events]]]mail from``
- ``[[[events]]]mail smtp``.

By default, a cylc suite will send you no more than one task event email every
5 minutes - this is to prevent your inbox from being flooded by emails should a
large group of tasks all fail at similar time.
See :ref:`task-event-mail-interval` for details.

Event handlers can be located in the suite ``bin/`` directory;
otherwise it is up to you to ensure their location is in ``$PATH`` (in
the shell in which the suite server program runs). They should require little
resource and return quickly - see :ref:`Managing External Command Execution`.

Task event handlers can be specified using the
``[[[events]]]<event> handler`` settings, where
``<event>`` is one of:

- 'submitted' - the job submit command was successful
- 'submission failed' - the job submit command failed
- 'submission timeout' - task job submission timed out
- 'submission retry' - task job submission failed, but will retry after
  a configured delay
- 'started' - the task reported commencement of execution
- 'succeeded' - the task reported successful completion
- 'warning' - the task reported a WARNING severity message
- 'critical' - the task reported a CRITICAL severity message
- 'custom' - the task reported a CUSTOM severity message
- 'late' - the task is never active and is late
- 'failed' - the task failed
- 'retry' - the task failed but will retry after a configured delay
- 'execution timeout' - task execution timed out

The value of each setting should be a list of command lines or command line
templates (see below).

Alternatively you can use ``[[[events]]]handlers`` and
``[[[events]]]handler events``, where the former is a list of command
lines or command line templates (see below) and the latter is a list of events
for which these commands should be invoked. (The name of a registered task
output can also be used as an event name in this case.)

Event handler arguments can be constructed from various templates
representing suite name; task ID, name, cycle point, message, and submit
number name; and any suite or task ``[meta]`` item.
See :ref:`SuiteEventHandling` and :ref:`TaskEventHandling` for options.

If no template arguments are supplied the following default command line
will be used:

.. code-block:: none

   <task-event-handler> %(event)s %(suite)s %(id)s %(message)s

.. note::

   Substitution patterns should not be quoted in the template strings.
   This is done automatically where required.

For an explanation of the substitution syntax, see
`String Formatting Operations
<https://docs.python.org/2/library/stdtypes.html#string-formatting>`_
in the Python documentation.

The retry event occurs if a task fails and has any remaining retries
configured (see :ref:`TaskRetries`).
The event handler will be called as soon as the task fails, not after
the retry delay period when it is resubmitted.

.. note::

   Event handlers are called by the suite server program, not by
   task jobs. If you wish to pass additional information to them use
   ``[cylc] -> [[environment]]``, not task runtime environment.

The following two ``suite.rc`` snippets are examples on how to specify
event handlers using the alternate methods:

.. code-block:: cylc

   [runtime]
       [[foo]]
           script = test ${CYLC_TASK_TRY_NUMBER} -eq 2
           [[[events]]]
               retry handler = "echo '!!!!!EVENT!!!!!' "
               failed handler = "echo '!!!!!EVENT!!!!!' "
           [[[job]]]
               execution retry delays = PT0S, PT30S

.. code-block:: cylc

   [runtime]
       [[foo]]
           script = """
               test ${CYLC_TASK_TRY_NUMBER} -eq 2
               cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" 'oopsy daisy'
           """
           [[[events]]]
               handlers = "echo '!!!!!EVENT!!!!!' "
               # Note: task output name can be used as an event in this method
               handler events = retry, failed, oops
           [[[job]]]
               execution retry delays = PT0S, PT30S
           [[[outputs]]]
               oops = oopsy daisy

The handler command here - specified with no arguments - is called with the
default arguments, like this:

.. code-block:: bash

   echo '!!!!!EVENT!!!!!' %(event)s %(suite)s %(id)s %(message)s


.. _Late Events:

Late Events
^^^^^^^^^^^

You may want to be notified when certain tasks are running late in a real time
production system - i.e. when they have not triggered by *the usual time*.
Tasks of primary interest are not normally clock-triggered however, so their
trigger times are mostly a function of how the suite runs in its environment,
and even external factors such as contention with other suites [3]_ .

But if your system is reasonably stable from one cycle to the next such that a
given task has consistently triggered by some interval beyond its cycle point,
you can configure Cylc to emit a *late event* if it has not triggered by
that time. For example, if a task ``forecast`` normally triggers by 30
minutes after its cycle point, configure late notification for it like this:

.. code-block:: cylc

   [runtime]
      [[forecast]]
           script = run-model.sh
           [[[events]]]
               late offset = PT30M
               late handler = my-handler %(message)s

*Late offset intervals are not computed automatically so be careful
to update them after any change that affects triggering times.*

.. note::

   Cylc can only check for lateness in tasks that it is currently aware
   of. If a suite gets delayed over many cycles the next tasks coming up
   can be identified as late immediately, and subsequent tasks can be
   identified as late as the suite progresses to subsequent cycle points,
   until it catches up to the clock.


.. _Managing External Command Execution:

Managing External Command Execution
-----------------------------------

Job submission commands, event handlers, and job poll and kill commands, are
executed by the suite server program in a "pool" of asynchronous
subprocesses, in order to avoid holding the suite up. The process pool is
actively managed to limit it to a configurable size (:ref:`process pool size`).
Custom event handlers should be light-weight and quick-running because they
will tie up a process pool member until they complete, and the suite will
appear to stall if the pool is saturated with long-running processes. Processes
are killed after a configurable timeout (:ref:`process pool timeout`) however,
to guard against rogue commands that hang indefinitely. All process kills are
logged by the suite server program. For killed job submissions the associated
tasks also go to the *submit-failed* state.


.. _PreemptionHPC:

Handling Job Preemption
-----------------------

Some HPC facilities allow job preemption: the resource manager can kill
or suspend running low priority jobs in order to make way for high
priority jobs. The preempted jobs may then be automatically restarted
by the resource manager, from the same point (if suspended) or requeued
to run again from the start (if killed).

Suspended jobs will poll as still running (their job status file says they
started running, and they still appear in the resource manager queue).
Loadleveler jobs that are preempted by kill-and-requeue ("job vacation") are
automatically returned to the submitted state by Cylc.  This is possible
because Loadleveler sends the SIGUSR1 signal before SIGKILL for preemption.
Other batch schedulers just send SIGTERM before SIGKILL as normal, so Cylc
cannot distinguish a preemption job kill from a normal job kill. After this the
job will poll as failed (correctly, because it was killed, and the job status
file records that). To handle this kind of preemption automatically you could
use a task failed or retry event handler that queries the batch scheduler queue
(after an appropriate delay if necessary) and then, if the job has been
requeued, uses ``cylc reset`` to reset the task to the submitted state.


Manual Task Triggering and Edit-Run
-----------------------------------

Any task proxy currently present in the suite can be manually triggered at any
time using the ``cylc trigger`` command, or from the right-click task
menu in gcylc. If the task belongs to a limited internal queue
(see :ref:`InternalQueues`), this will queue it; if not, or if it is already
queued, it will submit immediately.

With ``cylc trigger --edit`` (also in the gcylc right-click task menu)
you can edit the generated task job script to make one-off changes before the
task submits.


.. _cylc-broadcast:

Cylc Broadcast
--------------

The ``cylc broadcast`` command overrides ``[runtime]``
settings in a running suite. This can
be used to communicate information to downstream tasks by broadcasting
environment variables (communication of information from one task to
another normally takes place via the filesystem, i.e. the input/output
file relationships embodied in inter-task dependencies). Variables (and
any other runtime settings) may be broadcast to all subsequent tasks,
or targeted specifically at a specific task, all subsequent tasks with a
given name, or all tasks with a given cycle point; see broadcast command help
for details.

Broadcast settings targeted at a specific task ID or cycle point expire and
are forgotten as the suite moves on. Un-targeted variables and those
targeted at a task name persist throughout the suite run, even across
restarts, unless manually cleared using the broadcast command - and so
should be used sparingly.


The Meaning And Use Of Initial Cycle Point
------------------------------------------

When a suite is started with the ``cylc run`` command (cold or
warm start) the cycle point at which it starts can be given on the command
line or hardwired into the suite.rc file:

.. code-block:: bash

   cylc run foo 20120808T06Z

or:

.. code-block:: cylc

   [scheduling]
       initial cycle point = 20100808T06Z

An initial cycle given on the command line will override one in the
suite.rc file.


The Environment Variable CYLC\_SUITE\_INITIAL\_CYCLE\_POINT
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the case of a *cold start only* the initial cycle point is passed
through to task execution environments as
``$CYLC_SUITE_INITIAL_CYCLE_POINT``. The value is then stored in
suite database files and persists across restarts, but it does get wiped out
(set to ``None``) after a warm start, because a warm start is really an
implicit restart in which all state information is lost (except that the
previous cycle is assumed to have completed).

The ``$CYLC_SUITE_INITIAL_CYCLE_POINT`` variable allows tasks to
determine if they are running in the initial cold-start cycle point, when
different behaviour may be required, or in a normal mid-run cycle point.
Note however that an initial ``R1`` graph section is now the preferred
way to get different behaviour at suite start-up.


.. _SimulationMode:

Simulating Suite Behaviour
--------------------------

Several suite run modes allow you to simulate suite behaviour quickly without
running the suite's real jobs - which may be long-running and resource-hungry:

- *dummy mode* - runs dummy tasks as background jobs on configured
  job hosts.

  - simulates scheduling, job host connectivity, and
    generates all job files on suite and job hosts.

- *dummy-local mode* - runs real dummy tasks as background jobs on
  the suite host, which allows dummy-running suites from other sites.

  - simulates scheduling and generates all job files on the
    suite host.

- *simulation mode* - does not run any real tasks.

  - simulates scheduling without generating any job files.

Set the run mode (default *live*) in the GUI suite start dialog box, or on
the command line:

.. code-block:: bash

   $ cylc run --mode=dummy SUITE
   $ cylc restart --mode=dummy SUITE

You can get specified tasks to fail in these modes, for more flexible suite
testing. See :ref:`suiterc-sim-config` for simulation configuration.


Proportional Simulated Run Length
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If task ``[job]execution time limit`` is set, Cylc divides it by
``[simulation]speedup factor`` (default ``10.0``) to compute
simulated task run lengths (default 10 seconds).


Limitations Of Suite Simulation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dummy mode ignores batch scheduler settings because Cylc does not know which
job resource directives (requested memory, number of compute nodes, etc.) would
need to be changed for the dummy jobs.  If you need to dummy-run jobs on a
batch scheduler manually comment out ``script`` items and modify
directives in your live suite, or else use a custom live mode test suite.

.. note::

   The dummy modes ignore all configured task ``script`` items
   including ``init-script``. If your ``init-script`` is required
   to run even dummy tasks on a job host, note that host environment
   setup should be done
   elsewhere - see :ref:`Configure Site Environment on Job Hosts`.


Restarting Suites With A Different Run Mode?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The run mode is recorded in the suite run database files. Cylc will not let
you *restart* a non-live mode suite in live mode, or vice versa. To
test a live suite in simulation mode just take a quick copy of it and run the
the copy in simulation mode.


.. _AutoRefTests:

Automated Reference Test Suites
-------------------------------

Reference tests are finite-duration suite runs that abort with non-zero
exit status if any of the following conditions occur (by default):

- cylc fails
- any task fails
- the suite times out (e.g. a task dies without reporting failure)
- a nominated shutdown event handler exits with error status

The default shutdown event handler for reference tests is
``cylc hook check-triggering`` which compares task triggering
information (what triggers off what at run time) in the test run suite
log to that from an earlier reference run, disregarding the timing and
order of events - which can vary according to the external queueing
conditions, runahead limit, and so on.

To prepare a reference log for a suite, run it with the
``--reference-log`` option, and manually verify the
correctness of the reference run.

To reference test a suite, just run it (in dummy mode for the most
comprehensive test without running real tasks) with the
``--reference-test`` option.

A battery of automated reference tests is used to test cylc before
posting a new release version. Reference tests can also be used to check that
a cylc upgrade will not break your own complex
suites - the triggering check will catch any bug that causes a task to
run when it shouldn't, for instance; even in a dummy mode reference
test the full task job script (sans ``script`` items) executes on the
proper task host by the proper batch system.

Reference tests can be configured with the following settings:

.. code-block:: cylc

   [cylc]
       [[reference test]]
           suite shutdown event handler = cylc check-triggering
           required run mode = dummy
           allow task failures = False
           live mode suite timeout = PT5M
           dummy mode suite timeout = PT2M
           simulation mode suite timeout = PT2M


Roll-your-own Reference Tests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the default reference test is not sufficient for your needs, firstly
note that you can override the default shutdown event handler, and
secondly that the ``--reference-test`` option is merely a short
cut to the following suite.rc settings which can also be set manually if
you wish:

.. code-block:: cylc

   [cylc]
       abort if any task fails = True
       [[events]]
           shutdown handler = cylc check-triggering
           timeout = PT5M
           abort if shutdown handler fails = True
           abort on timeout = True


.. _SuiteStatePolling:

Triggering Off Of Tasks In Other Suites
---------------------------------------

.. note::

   Please read :ref:`External Triggers` before using
   the older inter-suite triggering mechanism described in this section.

The ``cylc suite-state`` command interrogates suite run databases. It
has a polling mode that waits for a given task in the target suite to achieve a
given state, or receive a given message. This can be used to make task
scripting wait for a remote task to succeed (for example).

Automatic suite-state polling tasks can be defined with in the graph. They get
automatically-generated task scripting that uses ``cylc suite-state``
appropriately (it is an error to give your own ``script`` item for these
tasks).

Here's how to trigger a task ``bar`` off a task ``foo`` in
a remote suite called ``other.suite``:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           [[[T00, T12]]]
               graph = "my-foo<other.suite::foo> => bar"

Local task ``my-foo`` will poll for the success of ``foo``
in suite ``other.suite``, at the same cycle point, succeeding only when
or if it succeeds. Other task states can also be polled:

.. code-block:: cylc

   graph = "my-foo<other.suite::foo:fail> => bar"

The default polling parameters (e.g. maximum number of polls and the interval
between them) are printed by ``cylc suite-state --help`` and can be
configured if necessary under the local polling task runtime section:

.. code-block:: cylc

   [scheduling]
       [[ dependencies]]
           [[[T00,T12]]]
               graph = "my-foo<other.suite::foo> => bar"
   [runtime]
       [[my-foo]]
           [[[suite state polling]]]
               max-polls = 100
               interval = PT10S

To poll for the target task to receive a message rather than achieve a state,
give the message in the runtime configuration (in which case the task status
inferred from the graph syntax will be ignored):

.. code-block:: cylc

   [runtime]
       [[my-foo]]
           [[[suite state polling]]]
               message = "the quick brown fox"

For suites owned by others, or those with run databases in non-standard
locations, use the ``--run-dir`` option, or in-suite:

.. code-block:: cylc

   [runtime]
       [[my-foo]]
           [[[suite state polling]]]
               run-dir = /path/to/top/level/cylc/run-directory

If the remote task has a different cycling sequence, just arrange for the
local polling task to be on the same sequence as the remote task that it
represents. For instance, if local task ``cat`` cycles 6-hourly at
``0,6,12,18`` but needs to trigger off a remote task ``dog``
at ``3,9,15,21``:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           [[[T03,T09,T15,T21]]]
               graph = "my-dog<other.suite::dog>"
           [[[T00,T06,T12,T18]]]
               graph = "my-dog[-PT3H] => cat"

For suite-state polling, the cycle point is automatically converted to the
cycle point format of the target suite.

The remote suite does not have to be running when polling commences because the
command interrogates the suite run database, not the suite server program.

.. note::

   The graph syntax for suite polling tasks cannot be combined with
   cycle point offsets, family triggers, or parameterized task notation.
   This does not present a problem because suite polling tasks can be put on
   the same cycling sequence as the remote-suite target task (as recommended
   above), and there is no point in having multiple tasks (family members or
   parameterized tasks) performing the same polling operation. Task state
   triggers can be used with suite polling, e.g. to trigger another task if
   polling fails after 10 tries at 10 second intervals:

   .. code-block:: cylc

      [scheduling]
          [[dependencies]]
              graph = "poller<other-suite::foo:succeed>:fail => another-task"
      [runtime]
          [[my-foo]]
              [[[suite state polling]]]
                  max-polls = 10
                  interval = PT10S


.. _Suite Server Logs:

Suite Server Logs
-----------------

Each suite maintains its own log of time-stamped events under the *suite
server log directory*:

.. code-block:: bash

   $HOME/cylc-run/SUITE-NAME/log/suite/

By way of example, we will show the complete server log generated (at
cylc-7.2.0) by a small suite that runs two 30-second dummy tasks
``foo`` and ``bar`` for a single cycle point
``2017-01-01T00Z`` before shutting down:

.. code-block:: cylc

   [cylc]
       cycle point format = %Y-%m-%dT%HZ
   [scheduling]
       initial cycle point = 2017-01-01T00Z
       final cycle point = 2017-01-01T00Z
       [[dependencies]]
           graph = "foo => bar"
   [runtime]
       [[foo]]
           script = sleep 30; /bin/false
       [[bar]]
           script = sleep 30; /bin/true

By the task scripting defined above, this suite will stall when ``foo``
fails. Then, the suite owner *vagrant@cylon* manually resets the failed
task's state to *succeeded*, allowing ``bar`` to trigger and the
suite to finish and shut down.  Here's the complete suite log for this run:

.. code-block:: none

   $ cylc cat-log SUITE-NAME
   2017-03-30T09:46:10Z INFO - Suite starting: server=localhost:43086 pid=3483
   2017-03-30T09:46:10Z INFO - Run mode: live
   2017-03-30T09:46:10Z INFO - Initial point: 2017-01-01T00Z
   2017-03-30T09:46:10Z INFO - Final point: 2017-01-01T00Z
   2017-03-30T09:46:10Z INFO - Cold Start 2017-01-01T00Z
   2017-03-30T09:46:11Z INFO - [foo.2017-01-01T00Z] -submit_method_id=3507
   2017-03-30T09:46:11Z INFO - [foo.2017-01-01T00Z] -submission succeeded
   2017-03-30T09:46:11Z INFO - [foo.2017-01-01T00Z] status=submitted: (received)started at 2017-03-30T09:46:10Z for job(01)
   2017-03-30T09:46:41Z CRITICAL - [foo.2017-01-01T00Z] status=running: (received)failed/EXIT at 2017-03-30T09:46:40Z for job(01)
   2017-03-30T09:46:42Z WARNING - suite stalled
   2017-03-30T09:46:42Z WARNING - Unmet prerequisites for bar.2017-01-01T00Z:
   2017-03-30T09:46:42Z WARNING -  * foo.2017-01-01T00Z succeeded
   2017-03-30T09:47:58Z INFO - [client-command] reset_task_states vagrant@cylon:cylc-reset 1e0d8e9f-2833-4dc9-a0c8-9cf263c4c8c3
   2017-03-30T09:47:58Z INFO - [foo.2017-01-01T00Z] -resetting state to succeeded
   2017-03-30T09:47:58Z INFO - Command succeeded: reset_task_states([u'foo.2017'], state=succeeded)
   2017-03-30T09:47:59Z INFO - [bar.2017-01-01T00Z] -submit_method_id=3565
   2017-03-30T09:47:59Z INFO - [bar.2017-01-01T00Z] -submission succeeded
   2017-03-30T09:47:59Z INFO - [bar.2017-01-01T00Z] status=submitted: (received)started at 2017-03-30T09:47:58Z for job(01)
   2017-03-30T09:48:29Z INFO - [bar.2017-01-01T00Z] status=running: (received)succeeded at 2017-03-30T09:48:28Z for job(01)
   2017-03-30T09:48:30Z INFO - Waiting for the command process pool to empty for shutdown
   2017-03-30T09:48:30Z INFO - Suite shutting down - AUTOMATIC

The information logged here includes:

- event timestamps, at the start of each line
- suite server host, port and process ID
- suite initial and final cycle points
- suite start type (cold start in this case)
- task events (task started, succeeded, failed, etc.)
- suite stalled warning (in this suite nothing else can run when
  ``foo`` fails)
- the client command issued by *vagrant@cylon* to reset
  ``foo`` to {\em succeeded}
- job IDs  - in this case process IDs for background jobs (or PBS job IDs
  etc.)
- state changes due to incoming task progress message  ("started at ..."
  etc.) suite shutdown time and reasons (AUTOMATIC means "all tasks finished
  and nothing else to do")

.. note::

   Suite log files are primarily intended for human eyes. If you need
   to have an external system to monitor suite events automatically,
   interrogate the sqlite *suite run database*
   (see :ref:`Suite Run Databases`) rather than parse the log files.


.. _Suite Run Databases:

Suite Run Databases
-------------------

Suite server programs maintain two ``sqlite`` databases to record
restart checkpoints and various other aspects of run history:

.. code-block:: bash

   $HOME/cylc-run/SUITE-NAME/log/db  # public suite DB
   $HOME/cylc-run/SUITE-NAME/.service/db  # private suite DB

The private DB is for use only by the suite server program. The identical
public DB is provided for use by external commands such as
``cylc suite-state``, ``cylc ls-checkpoints``, and
``cylc report-timings``. If the public DB gets locked for too long by
an external reader, the suite server program will eventually delete it and
replace it with a new copy of the private DB, to ensure that both correctly
reflect the suite state.

You can interrogate the public DB with the ``sqlite3`` command line tool,
the ``sqlite3`` module in the Python standard library, or any other
sqlite interface.

.. code-block:: bash

   $ sqlite3 ~/cylc-run/foo/log/db << _END_
   > .headers on
   > select * from task_events where name is "foo";
   > _END_
   name|cycle|time|submit_num|event|message
   foo|1|2017-03-12T11:06:09Z|1|submitted|
   foo|1|2017-03-12T11:06:09Z|1|output completed|started
   foo|1|2017-03-12T11:06:09Z|1|started|
   foo|1|2017-03-12T11:06:19Z|1|output completed|succeeded
   foo|1|2017-03-12T11:06:19Z|1|succeeded|


.. _Disaster Recovery:

Disaster Recovery
-----------------

If a suite run directory gets deleted or corrupted, the options for recovery
are:

- restore the run directory from back-up, and restart the suite
- re-install from source, and warm start from the beginning of the
  current cycle point

A warm start (see :ref:`Warm Start`) does not need a suite state
checkpoint, but it wipes out prior run history, and it could re-run
a significant number of tasks that had already completed.

To restart the suite, the critical Cylc files that must be restored are:

.. code-block:: bash

   # On the suite host:
   ~/cylc-run/SUITE-NAME/
       suite.rc   # live suite configuration (located here in Rose suites)
       log/db  # public suite DB (can just be a copy of the private DB)
       log/rose-suite-run.conf  # (needed to restart a Rose suite)
       .service/db  # private suite DB
       .service/source -> PATH-TO-SUITE-DIR  # symlink to live suite directory

   # On job hosts (if no shared filesystem):
   ~/cylc-run/SUITE-NAME/
       log/job/CYCLE-POINT/TASK-NAME/SUBMIT-NUM/job.status

.. note::

   This discussion does not address restoration of files generated and
   consumed by task jobs at run time. How suite data is stored and recovered
   in your environment is a matter of suite and system design.

In short, you can simply restore the suite service directory, the log
directory, and the suite.rc file that is the target of the symlink in the
service directory. The service and log directories will come with extra files
that aren't strictly needed for a restart, but that doesn't matter - although
depending on your log housekeeping the ``log/job`` directory could be
huge, so you might want to be selective about that.  (Also in a Rose suite, the
``suite.rc`` file does not need to be restored if you restart with
``rose suite-run`` - which re-installs suite source files to the run
directory).

The public DB is not strictly required for a restart - the suite server program
will recreate it if need be - but it is required by
``cylc ls-checkpoints`` if you need to identify the right restart
checkpoint.

The job status files are only needed if the restart suite state checkpoint
contains active tasks that need to be polled to determine what happened to them
while the suite was down.  Without them, polling will fail and those tasks will
need to be manually set to the correct state.

.. warning::

   It is not safe to copy or rsync a potentially-active sqlite DB - the copy
   might end up corrupted. It is best to stop the suite before copying
   a DB, or else write a back-up utility using the
   `official sqlite backup API <http://www.sqlite.org/backup.html>`_.


.. _auto-stop-restart:

Auto Stop-Restart
-----------------

Cylc has the ability to automatically stop suites running on a particular host
and optionally, restart them on a different host.
This is useful if a host needs to be taken off-line e.g. for
scheduled maintenance.

This functionality is configured via the following site configuration settings:

- ``[run hosts][suite servers]auto restart delay``
- ``[run hosts][suite servers]condemned hosts``
- ``[run hosts][suite servers]run hosts``

The auto stop-restart feature has two modes:

- [Normal Mode]

  - When a host is added to the ``condemned hosts`` list, any suites
    running on that host will automatically shutdown then restart selecting a
    new host from ``run hosts``.
  - For safety, before attempting to stop the suite cylc will first wait
    for any jobs running locally (under background or at) to complete.
  - *In order for Cylc to be able to successfully restart suites the
    ``run hosts`` must all be on a shared filesystem.*

- [Force Mode]

  - If a host is suffixed with an exclamation mark then Cylc will not attempt
    to automatically restart the suite and any local jobs (running under
    background or at) will be left running.

For example in the following configuration any suites running on
``foo`` will attempt to restart on ``pub`` whereas any suites
running on ``bar`` will stop immediately, making no attempt to restart.

.. code-block:: cylc

   [suite servers]
       run hosts = pub
       condemned hosts = foo, bar!

To prevent large numbers of suites attempting to restart simultaneously the
``auto restart delay`` setting defines a period of time in seconds.
Suites will wait for a random period of time between zero and
``auto restart delay`` seconds before attempting to stop and restart.

Suites that are started up in no-detach mode cannot be auto stop-restart on a
different host - as it will still end up attached to the condemned hosts.
Therefore, a suite in no-detach mode running on a condemned host will abort with
a non-zero return code. The parent process should manually handle the restart of
the suite if desired.

See the ``[suite servers]`` configuration section
(:ref:`global-suite-servers`) for more details.


.. [3] Late notification of clock-triggered tasks is not very useful in
       any case because they typically do not depend on other tasks, and as
       such they can often trigger on time even if the suite is delayed to
       the point that downstream tasks are late due to their dependence on
       previous-cycle tasks that are delayed.


.. _Alternate Suite Run Directories:

Alternate Suite Run Directories
-------------------------------

The ``cylc register`` command normally creates a suite run directory at
the standard location ``~/cylc-run/<SUITE-NAME>/``. With the ``--run-dir``
option it can create the run directory at some other location, with a symlink
from ``~/cylc-run/<SUITE-NAME>`` to allow access via the standard file path.

This may be useful for quick-running :ref:`Sub-Suites` that generate large
numbers of files - you could put their run directories on fast local disk or
RAM disk, for performance and housekeeping reasons.


.. _Sub-Suites:

Sub-Suites
----------

A single Cylc suite can configure multiple cycling sequences in the graph, but
cycles can't be nested. If you need *cycles within cycles* - e.g. to iterate
over many files generated by each run of a cycling task - current options are:

- parameterize the sub-cycles

  - this is easy but it makes more tasks-per-cycle, which is the primary
    determinant of suite size and server program efficiency

- run a separate cycling suite over the sub-cycle, inside a main-suite task,
  for each main-suite cycle point - i.e. use **sub-suites**

  - this is very efficient, but monitoring and run-directory housekeeping may
    be more difficult because it creates multiple suites and run directories

Sub-suites must be started with ``--no-detach`` so that the containing task
does not finish until the sub-suite does, and they should be non-cycling
or have a ``final cycle point`` so they don't keep on running indefinitely.

Sub-suite names should normally incorporate the main-suite cycle point (use
``$CYLC_TASK_CYCLE_POINT`` in the ``cylc run`` command line to start the
sub-suite), so that successive sub-suites can run concurrently if necessary and
do not compete for the same run directory. This will generate a new sub-suite
run directory for every main-suite cycle point, so you may want to put
housekeeping tasks in the main suite to extract the useful products from each
sub-suite run and then delete the sub-suite run directory.

For quick-running sub-suites that generate large numbers of files, consider
using :ref:`Alternate Suite Run Directories` for better performance and easier
housekeeping.
