#!/usr/bin/python

# system specific information for users, accessible via the command
# 'cylc system-info SYSTEM'.

info = """
This is an implementation of the example system used to illustrate the
Cylc Userguide. It consists of a set of shell scripts in the system
'scripts' sub-directory. It behaves just like a real forecasting system
as far as scheduling is concerned.

> HOW THE SYSTEM WORKS:
Each task "writes output files" using the touch command, and "reads
input files" by detecting the existence of the resulting empty files.

> RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE:
All tasks in this system read from and write to $TMPDIR, which is
defined in the system config module to be /tmp/$USER/{system-name}
(task-specific input and output directories could be configured
similarly via environment variables set in the task definitino files).
Thus if you register the system under several different names you can
run several instances of it at once. 

> GETTING TASKS TO FAIL ON DEMAND:
In real mode you can deliberately cause any task in this system to fail,
in order to see the effect this has on the system, by exporting
FAIL_TASK={NAME}%{CYCLE} before starting the scheduler.  This is
implemented in scripts/check-env.sh, which is called by all the other
task scripts: it checks for $FAIL_TASK and aborts if the value matches
the host task's identity. If the system is shutdown and restarted, or if
the failed task is reset in the running system, it will run
successfully (as would be the case in a real system after fixing the
problem). In dummy mode, the '--fail-out' option has a similar effect.

> ACCELERATED REAL TIME OPERATION:
Estimated task run times specified in the task definition files are
used only in dummy mode, and are scaled according to the dummy mode
clock rate.  However, this is an illustrative example system for which 
we also want fast real time operation. To achieve this, each task script
scales its real run time by $REAL_TIME_ACCEL, set in the system config module.
"""
