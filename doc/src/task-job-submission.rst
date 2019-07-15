.. _TaskJobSubmission:

Task Job Submission and Management
==================================

For the requirements a command, script, or program, must fulfill in order
to function as a cylc task, see :ref:`TaskImplementation`.
This section explains how tasks are submitted by the suite server program when
they are ready to run, and how to define new batch system handlers.

When a task is ready cylc generates a job script (see :ref:`JobScripts`). The
job script is submitted to run by the *batch system* chosen for
the task. Different tasks can use different batch systems.  Like
other runtime properties, you can set a suite default batch system and
override it for specific tasks or families:

.. code-block:: cylc

   [runtime]
      [[root]] # suite defaults
           [[[job]]]
               batch system = loadleveler
      [[foo]] # just task foo
           [[[job]]]
               batch system = at


.. _AvailableMethods:

Supported Job Submission Methods
--------------------------------

Cylc supports a number of commonly used batch systems.
See :ref:`CustomJobSubmissionMethods` for how to add new job
submission methods.


background
^^^^^^^^^^

Runs task job scripts as Unix background processes.

If an execution time limit is specified for a task, its job will be wrapped
by the ``timeout`` command.


at
^^

Submits task job scripts to the rudimentary Unix ``at`` scheduler. The
``atd`` daemon must be running.

If an execution time limit is specified for a task, its job will be wrapped
by the ``timeout`` command.


loadleveler
^^^^^^^^^^^

Submits task job scripts to loadleveler by the ``llsubmit`` command.
Loadleveler directives can be provided in the suite.rc file:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = loadleveler
               execution time limit = PT10M
           [[[directives]]]
               foo = bar
               baz = qux

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   # @ foo = bar
   # @ baz = qux
   # @ wall_clock_limit = 660,600
   # @ queue

If ``restart=yes`` is specified as a directive for loadleveler, the job will
automatically trap SIGUSR1, which loadleveler may use to preempt the job. On
trapping SIGUSR1, the job will inform the suite that it has been vacated by
loadleveler. This will put it back to the submitted state, until it starts
running again.

If ``execution time limit`` is specified, it is used to generate the
``wall_clock_limit`` directive. The setting is assumed to be the soft
limit. The hard limit will be set by adding an extra minute to the soft limit.
Do not specify the ``wall_clock_limit`` directive explicitly if
``execution time limit`` is specified. Otherwise, the execution time
limit known by the suite may be out of sync with what is submitted to the batch
system.


lsf
^^^

Submits task job scripts to IBM Platform LSF by the ``bsub`` command.
LSF directives can be provided in the suite.rc file:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = lsf
               execution time limit = PT10M
           [[[directives]]]
               -q = foo

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #BSUB -q = foo
   #BSUB -W = 10

If ``execution time limit`` is specified, it is used to generate the
``-W`` directive. Do not specify the ``-W`` directive
explicitly if ``execution time limit`` is specified. Otherwise, the
execution time limit known by the suite may be out of sync with what is
submitted to the batch system.


pbs
^^^

Submits task job scripts to PBS (or Torque) by the ``qsub`` command.
PBS directives can be provided in the suite.rc file:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = pbs
               execution time limit = PT1M
           [[[directives]]]
               -V =
               -q = foo
               -l nodes = 1

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #PBS -V
   #PBS -q foo
   #PBS -l nodes=1
   #PBS -l walltime=60

If ``execution time limit`` is specified, it is used to generate the
``-l walltime`` directive. Do not specify the ``-l walltime``
directive explicitly if ``execution time limit`` is specified.
Otherwise, the execution time limit known by the suite may be out of sync with
what is submitted to the batch system.


moab
^^^^

Submits task job scripts to the Moab workload manager by the ``msub``
command.  Moab directives can be provided in the suite.rc file; the syntax is
very similar to PBS:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = moab
               execution time limit = PT1M
           [[[directives]]]
               -V =
               -q = foo
               -l nodes = 1

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #PBS -V
   #PBS -q foo
   #PBS -l nodes=1
   #PBS -l walltime=60

(Moab understands ``#PBS`` directives).

If ``execution time limit`` is specified, it is used to generate the
``-l walltime`` directive. Do not specify the ``-l walltime``
directive explicitly if ``execution time limit`` is specified.
Otherwise, the execution time limit known by the suite may be out of sync with
what is submitted to the batch system.


sge
^^^

Submits task job scripts to Sun/Oracle Grid Engine by the ``qsub``
command.  SGE directives can be provided in the suite.rc file:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = sge
               execution time limit = P1D
           [[[directives]]]
               -cwd =
               -q = foo
               -l h_data = 1024M
               -l h_rt = 24:00:00

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   # DIRECTIVES
   #$ -cwd
   #$ -q foo
   #$ -l h_data=1024M
   #$ -l h_rt=24:00:00

If ``execution time limit`` is specified, it is used to generate the
``-l h_rt`` directive. Do not specify the ``-l h_rt``
directive explicitly if ``execution time limit`` is specified.
Otherwise, the execution time limit known by the suite may be out of sync with
what is submitted to the batch system.


slurm
^^^^^

Submits task job scripts to Simple Linux Utility for Resource Management by the
``sbatch`` command. SLURM directives can be provided in the suite.rc file:

.. code-block:: cylc

   [runtime]
       [[my_task]]
           [[[job]]]
               batch system = slurm
               execution time limit = PT1H
           [[[directives]]]
               --nodes = 5
               --account = QXZ5W2

.. note::

   Since not all SLURM commands have a short form, cylc requires
   the long form directives.

These are written to the top of the task job script like this:

.. code-block:: bash

   #!/bin/bash
   #SBATCH --nodes=5
   #SBATCH --time=60:00
   #SBATCH --account=QXZ5W2

If ``execution time limit`` is specified, it is used to generate the
``--time`` directive. Do not specify the ``--time``
directive explicitly if ``execution time limit`` is specified.
Otherwise, the execution time limit known by the suite may be out of sync with
what is submitted to the batch system.


Default Directives Provided
^^^^^^^^^^^^^^^^^^^^^^^^^^^

For batch systems that use job file directives (PBS, Loadleveler,
etc.) default directives are provided to set the job name, stdout and stderr
file paths, and the execution time limit (if specified).

Cylc constructs the job name string using a combination of the task ID and the
suite name. PBS fails a job submit if the job name in ``-N name`` is
too long. For version 12 or below, this is 15 characters. For version 13, this
is 236 characters. The default setting will truncate the job name string to 15
characters. If you have PBS 13 at your site, you should modify your site's
global configuration file to allow the job name to be longer. (See also
:ref:`JobNameLengthMaximum`.) For example:

.. code-block:: cylc

   [hosts]
       [[myhpc*]]
           [[[batch systems]]]
               [[[[pbs]]]]
                   # PBS 13
                   job name length maximum = 236


Directives Section Quirks (PBS, SGE, ...)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To specify an option with no argument, such as ``-V`` in PBS or
``-cwd`` in SGE you must give a null string as the directive value in
the suite.rc file.

The left hand side of a setting (i.e. the string before the first equal sign)
must be unique. To specify multiple values using an option such as
``-l`` option in PBS, SGE, etc., either specify all items in a single
line:

.. code-block:: none

   -l=select=28:ncpus=36:mpiprocs=18:ompthreads=2:walltime=12:00:00

(Left hand side is ``-l``. A second ``-l=...`` line will
override the first.)

Or separate the items:

.. code-block:: none

   -l select=28
   -l ncpus=36
   -l mpiprocs=18
   -l ompthreads=2
   -l walltime=12:00:00

.. note::

   There is no equal sign after ``-l``.

(Left hand sides are now ``-l select``, ``-l ncpus``, etc.)


.. _WhitherStdoutAndStderr:

Task stdout And stderr Logs
---------------------------

When a task is ready to run cylc generates a filename root to be used
for the task job script and log files. The filename containing the task
name, cycle point, and a submit number that increments if the same task is
re-triggered multiple times:

.. code-block:: bash

   # task job script:
   ~/cylc-run/tut/oneoff/basic/log/job/1/hello/01/job
   # task stdout:
   ~/cylc-run/tut/oneoff/basic/log/job/1/hello/01/job.out
   # task stderr:
   ~/cylc-run/tut/oneoff/basic/log/job/1/hello/01/job.err

How the stdout and stderr streams are directed into these files depends
on the batch system. The ``background`` method just uses
appropriate output redirection on the command line, as shown above. The
``loadleveler`` method writes appropriate directives to the job
script that is submitted to loadleveler.

Cylc obviously has no control over the stdout and stderr output from
tasks that do their own internal output management (e.g. tasks
that submit internal jobs and direct the associated output to other
files). For less internally complex tasks, however, the files referred
to here will be complete task job logs.

Some batch systems, such as ``pbs``, redirect a job's stdout
and stderr streams to a separate cache area while the job is running. The
contents are only copied to the normal locations when the job completes. This
means that ``cylc cat-log`` or the gcylc GUI will be unable to find the
job's stdout and stderr streams while the job is running. Some sites with these
batch systems are known to provide commands for viewing and/or
tail-follow a job's stdout and stderr streams that are redirected to these
cache areas. If this is the case at your site, you can configure cylc to make
use of the provided commands by adding some settings to the global site/user
config. E.g.:

.. code-block:: cylc

   [hosts]
       [[HOST]]  # <= replace this with a real host name
           [[[batch systems]]]
               [[[[pbs]]]]
                   err tailer = qcat -f -e \%(job_id)s
                   out tailer = qcat -f -o \%(job_id)s
                   err viewer = qcat -e \%(job_id)s
                   out viewer = qcat -o \%(job_id)s


.. _CommandTemplate:

Overriding The Job Submission Command
-------------------------------------

To change the form of the actual command used to submit a job you do not
need to define a new batch system handler; just override the
``command template`` in the relevant job submission sections of
your suite.rc file:

.. code-block:: cylc

   [runtime]
       [[root]]
           [[[job]]]
               batch system = loadleveler
               # Use '-s' to stop llsubmit returning
               # until all job steps have completed:
               batch submit command template = llsubmit -s %(job)s

As explained in :ref:`SuiteRCReference`
the template's \%(job)s will be substituted by the job file path.


Job Polling
-----------

For supported batch systems, one-way polling can be used to determine actual
job status: the suite server program executes a process on the task host, by
non-interactive ssh, to interrogate the batch queueing system there, and to
read a *status file* that is automatically generated by the task job script
as it runs.

Polling may be required to update the suite state correctly after unusual
events such as a machine being rebooted with tasks running on it, or network
problems that prevent task messages from getting back to the suite host.

Tasks can be polled on demand by right-clicking on them in gcylc or using the
``cylc poll`` command.

Tasks are polled automatically, once, if they timeout while queueing in a
batch scheduler and submission timeout is set. (See :ref:`TaskEventHandling`
for how to configure timeouts).

Tasks are polled multiple times, where necessary, when they exceed their
execution time limits. These are normally set with some initial delays to allow
the batch systems to kill the jobs.
(See :ref:`ExecutionTimeLimitPollingIntervals` for how to configure the polling
intervals).

Any tasks recorded in the *submitted* or *running* states at suite
restart are automatically polled to determine what happened to them while the
suite was down.

Regular polling can also be configured as a health check on tasks submitted to
hosts that are known to be flaky, or as the sole method of determining task
status on hosts that do not allow task messages to be routed back to the suite
host.

To use polling instead of task-to-suite messaging set
``task communication method = poll``
in cylc site and user global config (see :ref:`task_comms_method`).
The default polling intervals can be overridden for all suites there too
(see :ref:`submission_polling` and :ref:`execution_polling`), or in specific
suite configurations (in which case polling will be done regardless of the
task communication method configured for the host;
see :ref:`SubmissionPollingIntervals` and :ref:`ExecutionPollingIntervals`).

Note that regular polling is not as efficient as task messaging in updating
task status, and it should be used sparingly in large suites.

.. note::

   For polling to work correctly, the batch queueing system must have a
   job listing command for listing your jobs, and that the job listing must
   display job IDs as they are returned by the batch queueing system submit
   command. For example, for pbs, moab and sge, the ``qstat`` command
   should list jobs with their IDs displayed in exactly the same format as they
   are returned by the ``qsub`` command.


Job Killing
-----------

For supported batch systems, the suite server program can execute a process on
the task host, by non-interactive ssh, to kill a submitted or running job
according to its batch system.

Tasks can be killed on demand by right-clicking on them in gcylc or using the
``cylc kill`` command.


Execution Time Limit
--------------------

You can specify an ``execution time limit`` for all supported job
submission methods. E.g.:

.. code-block:: cylc

   [runtime]
       [[task-x]]
           [[[job]]]
               execution time limit = PT1H

For tasks running with ``background`` or ``at``, their jobs
will be wrapped using the ``timeout`` command. For all other methods,
the relevant time limit directive will be added to their job files.

The ``execution time limit`` setting will also inform the suite when a
a task job should complete by. If a task job has not reported completing within
the specified time, the suite will poll the task job. (The default
setting is PT1M, PT2M, PT7M. The accumulated times for these intervals will be
roughly 1 minute, 1 + 2 = 3 minutes and 1 + 2 + 7 = 10 minutes after a task job
exceeds its execution time limit.)


Execution Time Limit and Execution Timeout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you specify an ``execution time limit`` the
``execution timeout event handler`` will only be called if the job has
not completed after the final poll (by default, 10 min after the time limit).
This should only happen if the submission method you are using is not enforcing
wallclock limits (unlikely) or you are unable to contact the machine to confirm
the job status.

If you specify an ``execution timeout`` and not an
``execution time limit`` then the
``execution timeout event handler`` will be called as soon as the
specified time is reached. The job will also be polled to check its latest
status (possibly resulting in an update in its status and the calling of the
relevant event handler). This behaviour is deprecated, which users should avoid
using.

If you specify an ``execution timeout`` and an
``execution time limit`` then the execution timeout setting will be
ignored.


.. _CustomJobSubmissionMethods:

Custom Job Submission Methods
-----------------------------

Defining a new batch system handler requires a little Python programming. Use
the built-in handlers as examples, and read the documentation in
``lib/cylc/batch_sys_manager.py``.


An Example
^^^^^^^^^^

The following ``qsub.py`` module overrides the built-in *pbs*
batch system handler to change the directive prefix from ``#PBS`` to
``#QSUB``:

.. code-block:: python

   #!/usr/bin/env python2

   from cylc.batch_sys_handlers.pbs import PBSHandler

   class QSUBHandler(PBSHandler):
       DIRECTIVE_PREFIX = "#QSUB "

   BATCH_SYS_HANDLER = QSUBHandler()

If this is in the Python search path (see
:ref:`Where To Put Batch System Handler Modules` below) you can use it by
name in suite configurations:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           graph = "a"
   [runtime]
       [[root]]
           [[[job]]]
               batch system = qsub  # <---!
               execution time limit = PT1M
           [[[directives]]]
               -l nodes = 1
               -q = long
               -V =

Generate a job script to see the resulting directives:

.. code-block:: bash

   $ cylc register test $HOME/test
   $ cylc jobscript test a.1 | grep QSUB
   #QSUB -e /home/oliverh/cylc-run/my.suite/log/job/1/a/01/job.err
   #QSUB -l nodes=1
   #QSUB -l walltime=60
   #QSUB -o /home/oliverh/cylc-run/my.suite/log/job/1/a/01/job.out
   #QSUB -N a.1
   #QSUB -q long
   #QSUB -V

(Of course this suite will fail at run time because we only changed the
directive format, and PBS does not accept ``#QSUB`` directives in
reality).


.. _Where To Put Batch System Handler Modules:

Where To Put Batch System Handler Modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Custom batch system handlers must be installed on suite and job
hosts* in one of these locations:

- under ``SUITE-DEF-PATH/lib/python/``
- under ``CYLC-PATH/lib/cylc/batch_sys_handlers/``
- or anywhere in ``$PYTHONPATH``

.. note::

   For Rose users: ``rose suite-run`` automatically installs
   ``SUITE-DEF-PATH/lib/python/`` to job hosts).
