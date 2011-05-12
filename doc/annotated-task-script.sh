#!/bin/bash

# THIS ANNOTATED CYLC TASK SCRIPT shows how to handle cylc messaging
# manually. THIS IS ONLY REQUIRED for (a) tasks with internal outputs
# that have to be reported complete before the task is finished, and (b)
# tasks that are not started and finished by the same process, in which
# case the process that finishes the job must do the final messaging.

# TRAP ERRORS: automatically report failure and release my task lock
# (means we don't have to check success of all operations manually)
set -e; trap 'cylc task failed "error trapped"' ERR

# ACQUIRE A TASK LOCK AND REPORT STARTED 
# inline error checking avoids the ERR trap (here 'cylc task started'
# reports failure to cylc itself so we don't want to invoke the trap).
cylc task started || exit 1

# Scripting errors etc will be caught by the ERR trap:
mkdir /illegal/dir/path  # trapped!

# Cylc-aware subprocesses that call 'task failed' on error:
cylc-aware-script || exit 1  # just exit on error

# Non-cylc-aware subprocess that just 'exit 1' on error:
non-cylc-aware || { # INLINE CHECK
    # handle error ...
    cylc task failed "non-cylc-aware script failed"
    exit 1
}
non-cylc-aware      # trap will abort on failure here ...
if [[ $? != 0 ]]; then # ... and this code will not be reached!
    # ...
fi

# send a progress message to my parent suite:
cylc task message "Hello World"

# REPORT ANY EXPLICIT OUTPUTS (TaskA:foo in dependency graph):
# one at a time:
cylc task message "File foo completed for for $CYCLE_TIME"
# ... or all at once: 
cylc task message --all-outputs-completed

# RELEASE TASK LOCK AND REPORT FINISHED:
cylc task finished
