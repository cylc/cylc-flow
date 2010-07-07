#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# THIS IS AN ANNOTATED CYLC TASK SCRIPT

#__1______________________________________________________ERROR_TRAPPING
# On error, report failure and release my task lock
set -e; trap 'cylc task-failed "error trapped"' ERR

#__2_______________________________________________________________START
# Acquire a task lock and report started 
#  o If 'cylc task-started' cannot acquire a task lock it will report
#    failure to cylc and exit with error status. This implies another
#    instance of the same task (NAME%CYCLE) could still be running,
#    perhaps left over from a recent hard shutdown of the system. If so
#    we must exit manually to avoid the ERR trap - which would otherwise
#    call task-failed a second time and erroneously remove the lock.
cylc task-started || exit 1

#__3_____________________________________________________TASK_PROCESSING
# Can be done:
#  o in this script
# and/or by:
#  o invoking other scripts and executables ("sub-processes", below)

# Sub-processes (and sub-sub-processes, etc.) that do not detach from
# this script: 
#  o MUST EXIT WITH NON-ZERO STATUS ON FAILURE
#    + so this script can check for success
#  o MUST NOT CALL cylc task-started OR task-finished
#    + this script does that
#  o MAY CALL cylc task-message AND task-failed ("cylc-aware", below)

# If the final task sub-process detaches from this script (e.g. this
# script submits a job to loadleveller and then exits), it:
#  o MUST CALL cylc task-finished OR task-failed when done.
#    + this script can't because it has exited.

# For cylc-aware sub-processes:
#  o messages are logged by cylc, including the reason for a failure
#  o failure must be detected manually in this script or the ERR trap
#    will result in a second call to 'cylc task-failed'.

cylc-aware-script || exit 1         # manual exit on error (not trapped)

# Non-cylc-aware sub-processes:
#  o output appears in task stdout and stderr, but not the cylc log
#  o failure can be trapped automatically OR manually detected 

non-cylc-aware-script_1                     # leave it to the error trap

if ! non-cylc-aware-script_2; then
    cylc task-failed "non-cylc-aware-script_2 failed"           # manual
    exit 1
fi

# send a progress message
cylc task-message "Hello World"

# report a registered output complete
cylc task-message "sent one progress message for $CYCLE_TIME"

# execute an external program
if ! run_atmos_model; then
    cylc task-failed "model failed"
    exit 1
fi

#__________________________________________________________REPORT OUTPUTS
# if atmos_model does not report its own outputs as it runs we can cheat
cylc task-message --all-outputs-completed

#__________________________________________________________________FINISH
# release the task lock and report finished
cylc task-finished
