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
| Each task generates empty output files using the touch command, and     |
| "reads" empty input files, aborting if they do not exist                |
|_________________________________________________________________________|
| + RUNNING MULTIPLE SYSTEM INSTANCES AT ONCE                             |
| All task I/O is done under $CYLC_TMPDIR, defined at run time to include |
| the registered system name (see systems/userguide/system_config.py).    |
| Thus if you register the system under multiple names you can run        | 
| system instances at once without any interference between them.         |
|_________________________________________________________________________|
| + GETTING TASKS TO FAIL ON DEMAND IN REAL MODE OPERATION                |
| For this example system only, before starting the system set:           |
|   $ export FAIL_TASK=TaskC%2010010106                                   |
| This causes TaskC to abort (via systems/userguide/scripts/check-env.sh )|
| If the task is subsequently reset, or the system restarted, the task    |
| will not abort again, as if the "problem" had been fixed.               |
|   NOTE in DUMMY MODE you can do the same for ANY system, by using the   |
| '--fail=TaskC%2010010106' commandline option at startup.           |
|_________________________________________________________________________|
| + REAL TIME OPERATION                                                   |
| The tasks in this system are designed to run quickly (~5 seconds), but  |
| note that if the system catches up to real time operation there will be |
| a real 6 hour delay between cycles - so you might want to make sure the |
| initial cycle time is signficantly in the past. This is not an issue in |
| dummy mode, however, because of the accelerated dummy mode clock.       |
|_________________________________________________________________________|
"""

