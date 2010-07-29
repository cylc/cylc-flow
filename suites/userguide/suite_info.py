#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# suite specific information accessible via 'cylc show SUITE'.

info = """
___________________________________________________________________________
| This implements the cylc userguide example suite, tasks A,B,C,D,E,F,X.  |
| + HOW THE SUITE WORKS                                                   |
| Each task generates empty output files using the touch command, and     |
| "reads" empty input files, aborting if they do not exist                |
|_________________________________________________________________________|
| + RUNNING MULTIPLE SUITE INSTANCES AT ONCE                              |
| All task I/O is done under $CYLC_TMPDIR, defined at run time to include |
| the registered suite name (see suites/userguide/suite_config.py).       |
| Thus if you register the suite under multiple names you can run         | 
| suite instances at once without any interference between them.          |
|_________________________________________________________________________|
| + GETTING TASKS TO FAIL ON DEMAND IN REAL MODE OPERATION                |
| For this example suite only, before starting the suite set:             |
|   $ export FAIL_TASK=TaskC%2010010106                                   |
| This causes TaskC to abort (via suites/userguide/scripts/check-env.sh ) |
| If the task is subsequently reset, or the suite restarted, the task     |
| will not abort again, as if the "problem" had been fixed.               |
|   NOTE in DUMMY MODE you can do the same for ANY suite, by using the    |
| '--fail=TaskC%2010010106' commandline option at startup.                |
|_________________________________________________________________________|
| + REAL TIME OPERATION                                                   |
| The tasks in this suite are designed to run quickly (~5 seconds), but   |
| note that if the suite catches up to real time operation there will be  |
| a real 6 hour delay between cycles - so you might want to make sure the |
| initial cycle time is signficantly in the past. This is not an issue in |
| dummy mode, however, because of the accelerated dummy mode clock.       |
|_________________________________________________________________________|
"""

