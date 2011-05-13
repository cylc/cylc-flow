#!/bin/bash

# TRAP ERRORS: automatically report failure and release my task lock
# (so we don't have to check success of all operations manually)
set -e; trap 'cylc task failed "error trapped"' ERR

# When using 'set -e' (abort on error) EXPLICIT CHECKS MUST BE INLINE:
/bin/false
if [[ $? != 0 ]]; then  # WRONG: this will never be executed.
    # handle error
fi

/bin/false || {         # CORRECT; this avoids the 'set -e' trap
    # handle error
}

# ACQUIRE A TASK LOCK AND REPORT STARTED 
# Just 'exit 1' on failure as 'task started' calls 'task failed' itself.
cylc task started || exit 1

# Scripting errors etc will be caught and reported by the ERR trap:
mkdir /illegal/dir/path  # trapped!

# Cylc-aware subprocesses that call 'task failed' themselves on error:
cylc-aware-script || exit 1  # just exit on error

# Non-cylc-aware subprocesses that just 'exit 1' on error:
non-cylc-aware || { 
    cylc task failed "non-cylc-aware script failed"
    exit 1
}

# send a progress message to my parent suite:
cylc task message "Hello World"

# REPORT ANY EXPLICIT OUTPUTS (TaskA:foo in dependency graph):
# one at a time:
cylc task message "File foo completed for for $CYCLE_TIME"
# ... or all at once: 
cylc task message --all-outputs-completed

# RELEASE TASK LOCK AND REPORT FINISHED:
# Do this after all task processing is finished (probably not in the
# same script as 'task started' or you might as well wrap the task).
cylc task finished
