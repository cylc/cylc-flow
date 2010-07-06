#!/usr/bin/env python

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
___________________________________________________________________________
| This implements the cylc userguide example system, tasks A,B,C,D,E,F,X. |
| + HOW THE SYSTEM WORKS                                                  |
| Each task aborts if its expected input files do not exist (but does not |
| use them), and then creates its (empty) output files using 'touch'.     |
|_________________________________________________________________________|
| + RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE                             |
| All task I/O is done under $CYLC_TMPDIR, defined at run time to include |
| the registered system name (see systems/userguide/system_config.py).    |
| Thus if you register the system under multiple names you can run        | 
| system instances at once without any interference between them.         |
|_________________________________________________________________________|
| + GETTING TASKS TO FAIL ON DEMAND IN REAL MODE OPERATION                |
| Set $FAIL_TASK in the system config file, e.g.:                         |
|    self.items['environment']['FAIL_TASK'] = 'A%2010010106'              |
| The task will self-abort via systems/userguide/scripts/check-env.sh.    |
| If the task is reset, or the system restarted, it will run successfully |
| as if the "problem" has been fixed.                                     |                           
|                                                                         |
| Note: this is system-specific, but you can do the same thing for any    |
| system in DUMMY MODE using 'cylc (re)start -d --fail-task=A%2010010106' |
|_________________________________________________________________________|
| + REAL TIME OPERATION                                                   |
| The tasks in this system are designed to run quickly (~5 seconds), but  |
| note that if the system catches up to real time operation there will be |
| a real 6 hour delay between cycles - so you might want to make sure the |
| initial cycle time in signficantly in the past. This is not an issue in |
| dummy mode, however, because of the accelerated dummy mode clock.       |
|_________________________________________________________________________|
"""

