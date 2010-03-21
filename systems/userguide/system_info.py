#!/usr/bin/python

# system specific information for users, accessible via the command
# 'cylc system-info SYSTEM'.

info = """
This system implements the primary Cylc Userguide example, as a set of
shell scripts in the system definition 'scripts' sub-directory. 

> HOW THE SYSTEM WORKS:
Each task "writes output files" using the touch command, and "reads
input files" by detecting the existence of the required input files.
Thus, while obviously not a real forecasting system, it behaves the same
as a real system as far as scheduling is concerned.

> RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE:
All system read from and write to $TMPDIR, which is defined in the
system config module to be /tmp/$USER/{registered system name}. 
Thus if you register the system under several different names you can
run multiple instances of it at once. The same can be achieved with
task-specific input and output directories, by defining task-specific 
environment variables in the task definition files.

> GETTING TASKS TO FAIL ON DEMAND:
In real mode, you can deliberately cause any task in this system to
fail, in order to see the effect this has on the system, by exporting
FAIL_TASK={NAME}%{CYCLE} before starting the scheduler.  This is
implemented in scripts/check-env.sh, which is called by all the other
task scripts: it checks for $FAIL_TASK and aborts if the value matches
the task identity. If the failed task is restarted it will run
successfully, as it would in a real system after the problem been fixed.
Note that in dummy mode, the '--fail-out' option has a similar effect.

> ACCELERATED REAL TIME OPERATION:
Estimated task run times specified in the task definition files are
used only in dummy mode, and are scaled according to the dummy mode
clock rate.  Howver, in order to get fast real operation too, for this
simple example system, each task script scales its real run time by
$REAL_TIME_ACCEL, which is set in the system config module.
"""
