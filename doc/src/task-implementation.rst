.. _TaskImplementation:

Task Implementation
===================

Existing scripts and executables can be used as cylc tasks without modification
so long as they return standard exit status - zero on success, non-zero
for failure - and do not spawn detaching processes internally
(see :ref:`DetachingJobs`).


.. _JobScripts:

Task Job Scripts
----------------

When the suite server program determines that a task is ready to run it
generates a *job script* for the task, and submits it to run (see
:ref:`TaskJobSubmission`).

Job scripts encapsulate configured task runtime settings: ``script`` and
``environment`` items, if defined, are just concatenated in the order shown in
:numref:`fig-anatomy-of-a-job-script`, to make the job script. Everything
executes in the same shell, so each part of the script can potentially affect
the environment of subsequent parts.

.. _fig-anatomy-of-a-job-script:

.. figure:: graphics/png/orig/anatomy-of-a-job-script.png
   :align: center

   The order in which task runtime script and environment configuration items
   are combined, in the same shell, to create a task job script. ``cylc-env``
   represents Cylc-defined environment variables, and ``user-env`` user-defined
   variables from the task ``[environment]`` section. (Note this is not a suite
   dependency graph).

Task job scripts are written to the suite's job log directory. They can be
printed with ``cylc cat-log`` or generated and printed with
``cylc jobscript``.

Inlined Tasks
-------------

Task *script* items can be multi-line strings of ``bash``  code, so
many tasks can be entirely inlined in the suite.rc file. For anything more than
a few lines of code, however, we recommend using external shell scripts to allow
independent testing, re-use, and shell mode editing.


Task Messages
-------------

Tasks messages can be sent back to the suite server program to report completed
outputs and arbitrary messages of different severity levels.

Some types of message - in addition to events like task failure -  can
optionally trigger execution of event handlers in the suite server program
(see :ref:`EventHandling`).

Normal severity messages are printed to ``job.out`` and logged by the
suite server program:

.. code-block:: bash

   cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" \
     "Hello from ${CYLC_TASK_ID}"

CUSTOM severity messages are printed to ``job.out``, logged by the
suite server program, and can be used to trigger *custom*
event handlers:

.. code-block:: bash

   cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" \
     "CUSTOM:data available for ${CYLC_TASK_CYCLE_POINT}"

Custom severity messages and event handlers can be used to signal special
events that are neither routine information or an error condition, such as
production of a particular data file. Task output messages, used for triggering
other tasks, can also be sent with custom severity if need be.

WARNING severity messages are printed to ``job.err``, logged by the
suite server program, and can be passed to *warning* event handlers:

.. code-block:: bash

   cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" \
     "WARNING:Uh-oh, something's not right here."

CRITICAL severity messages are printed to ``job.err``, logged by the
suite server program, and can be passed to *critical* event handlers:

.. code-block:: bash

   cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" \
     "CRITICAL:ERROR occurred in process X!"


Aborting Job Scripts on Error
-----------------------------

Task job scripts use ``set -x`` to abort on any error, and
trap ERR, EXIT, and SIGTERM to send task failed messages back to the
suite server program before aborting. Other scripts called from job scripts
should therefore abort with standard non-zero exit status on error, to trigger
the job script error trap.

To prevent a command that is expected to generate a non-zero exit status from
triggering the exit trap, protect it with a control statement such as:

.. code-block:: bash

   if cmp FILE1 FILE2; then
       :  # success: do stuff
   else
       :  # failure: do other stuff
   fi

Task job scripts also use ``set -u`` to abort on referencing any
undefined variable (useful for picking up typos); and ``set -o pipefail``
to abort if any part of a pipe fails (by default the shell only returns the
exit status of the final command in a pipeline).


Custom Failure Messages
^^^^^^^^^^^^^^^^^^^^^^^

Critical events normally warrant aborting a job script rather than just sending
a message. As described just above, ``exit 1`` or any failing command
not protected by the surrounding scripting will cause a job script to abort and
report failure to the suite server program, potentially triggering a
*failed* task event handler.

For failures detected by the scripting you could send a critical message back
before aborting, potentially triggering a *critical* task event handler:

.. code-block:: bash

   if ! /bin/false; then
     cylc message -- "${CYLC_SUITE_NAME}" "${CYLC_TASK_JOB}" \
       "CRITICAL:ERROR: /bin/false failed!"
     exit 1
   fi

To abort a job script with a custom message that can be passed to a
*failed* task event handler, use the built-in ``cylc__job_abort`` shell
function:

.. code-block:: bash

   if ! /bin/false; then
     cylc__job_abort "ERROR: /bin/false failed!"
   fi


.. _DetachingJobs:

Avoid Detaching Processes
-------------------------

If a task script starts background sub-processes and does not wait on them, or
internally submits jobs to a batch scheduler and then exits immediately, the
detached processes will not be visible to cylc and the task will appear to
finish when the top-level script finishes. You will need to modify scripts
like this to make them execute all sub-processes in the foreground (or use the
shell ``wait`` command to wait on them before exiting) and to prevent
job submission commands from returning before the job completes (e.g.
``llsubmit -s`` for Loadleveler,
``qsub -sync yes`` for Sun Grid Engine, and
``qsub -W block=true`` for PBS).

If this is not possible - perhaps you don't have control over the script
or can't work out how to fix it - one alternative approach is to use another
task to repeatedly poll for the results of the detached processes:

.. code-block:: cylc

   [scheduling]
       [[dependencies]]
           graph = "model => checker => post-proc"
   [runtime]
       [[model]]
           # Uh-oh, this script does an internal job submission to run model.exe:
           script = "run-model.sh"
       [[checker]]
           # Fail and retry every minute (for 10 tries at the most) if model's
           # job.done indicator file does not exist yet.
           script = "[[ ! -f $RUN_DIR/job.done ]] && exit 1"
           [[[job]]]
               execution retry delays = 10 * PT1M
