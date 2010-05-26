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
An implementation of the task set that illustrates the cylc userguide.
______________________
HOW THE SYSTEM WORKS
Each task "writes output files" using the touch command, and "reads
input files" by detecting the existence of these (empty) files.
___________________________________________
RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE 
All tasks in this system read from and write to $CYLC_TMPDIR, which is
defined in the system config module to be /tmp/$USER/{system-name}
Thus if you register the system under several different names you can
run multiple instances of it at once. 
_________________________________
GETTING TASKS TO FAIL ON DEMAND 
You can cause any task in THIS SYSTEM to fail via the system config file: 
    self.items['environment']['FAIL_TASK'] = 'A%2010010106'
(the identified task will self-abort via scripts/check-env.sh).
If failed task is reset or the system restarted, the task will not fail
again (as would be the case after fixing a problem in a real system). 
The 'cylc start --dummy-mode --fail-out=A%2010010106' has the same
effect on ANY SYSTEM but ONLY IN DUMMY MODE.
_________________________________
ACCELERATED REAL TIME OPERATION 
Each task script scales its registered run time by $REAL_TIME_ACCEL as
defined in the system config file, so that the system can run as quickly
in real mode as it does in dummy mode.  HOWEVER, this will not speed up
CYCLING when the system catches up to real time operation (because the 
contact task X will trigger off the real wall clock time.)"""
