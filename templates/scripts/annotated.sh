#!/bin/bash

# THIS IS AN ANNOTATED CYLC TASK SCRIPT

# A cylc "task" must:
#  + send a "task started" message at startup
#  + report registered outputs completed, any time before it finishes 
#  + send a "task finished" message on successful completion
#  + send a "task failed" message in case of failure

# This example is a single monolithic script, but it does not have to
# be - so long as the first script invoked sends the started message
# and the last the finished message.  

# TRAP ERRORS: automatically report failure and release my task lock
# (means we don't have to check success of all operations manually)
set -e; trap 'cylc task-failed "error trapped"' ERR

# ACQUIRE A TASK LOCK AND REPORT STARTED 
# inline error checking avoids the ERR trap (here 'cylc task-started'
# reports failure to cylc itself so we don't want to invoke the trap).
cylc task-started || exit 1

# Scripting errors etc will be caught by the ERR trap
mkdir /illegal/dir/path

# Cylc-aware scripts or exes call 'task-failed' themselves on error
cylc-aware-script || exit 1

# DO NOT DO THIS:
cylc-aware-script
if [[ $? != 0 ]]; then
    # this line will never be reached because of the ERR trap above
fi

# Non-cylc-aware scripts or exes 'exit 1' on error - leave to the trap.
non-cylc-aware-script_1            

# or inline manual check if you prefer:
if ! non-cylc-aware-script_2; then
    cylc task-failed "non-cylc-aware-script_2 failed"
    exit 1
fi

# send a progress message
cylc task-message "Hello World"

# REPORT OUTPUTS (just messages that are registered as task outputs)
cylc task-message "sent one progress message for $CYCLE_TIME"

# If model does not report its own outputs as it runs we can cheat now
cylc task-message --all-outputs-completed

# FINISH
# release the task lock and report finished
cylc task-finished
