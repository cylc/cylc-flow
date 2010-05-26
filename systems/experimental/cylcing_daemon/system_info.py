#!/usr/bin/python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# system specific information for users, accessible via the command
# 'cylc system-info SYSTEM'.

info = """
This is an implementation of the example system used to illustrate the
first section of the Cylc Userguide.

> HOW THE SYSTEM WORKS:
Each task "writes output files" using the touch command, and "reads
input files" by detecting the existence of these (empty) files.

> RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE:
All tasks in this system read from and write to $CYLC_TMPDIR, which is
defined in the system config module to be /tmp/$USER/{system-name}
Thus if you register the system under several different names you can
run multiple instances of it at once. 

> GETTING TASKS TO FAIL ON DEMAND:
In real mode you can deliberately cause any task in THIS SYSTEM to fail
by defining an environment variable called FAIL_TASK in the system 
config file: 
        self.items['environment']['FAIL_TASK'] = 'A%2010010106'
(the identified task will self-abort, via scripts/check-env.sh).
If the system is then shutdown and restarted, or if the failed task is
reset in the running system, it will run successfully (as would be the
case in a real system after fixing the problem). In dummy mode, the
'--fail-out' option has a similar effect (for any system).

> ACCELERATED REAL TIME OPERATION:
As this is an illustrative example system, we want fast real mode
operation, similarly as in dummy mode. Accordingly each task script
scales its designated run time by $REAL_TIME_ACCEL, defined in the
system config module.  BE AWARE that this will not speed up CYCLING
if the system catches up to real time operation (the contact task X, on
which everything else depends, will only trigger once every 6 hours)"""
