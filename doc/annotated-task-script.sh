#!/bin/bash

# TRAP ERRORS: automatically report failure and release my task lock
# (so we don't have to check success of all operations manually)
set -e; trap 'cylc task failed "error trapped"' ERR

# ACQUIRE A TASK LOCK AND REPORT STARTED 
# Just 'exit 1' on failure as 'task started' calls 'task failed' itself.
cylc task started || exit 1

# When using 'set -e' (abort on error) EXPLICIT CHECKS MUST BE INLINE:
/bin/false
if [[ $? != 0 ]]; then  # WRONG: this will never be executed.
    # handle error
fi

/bin/false || {         # CORRECT; this avoids the 'set -e' trap
    # handle error
}

if ! /bin/false; then   # CORRECT; this avoids the 'set -e' trap
    # handle error
fi

# errors not explicitly handled will be caught by trapping:
mkdir /illegal/dir/path  # trapped!

# Cylc-aware subprocesses that call 'task failed' themselves on error
# should not be left to the trap (it would call 'task failed' again):
cylc-aware-script || exit 1 
# or this is OK too:
if ! cylc-aware-script; then
    # script failed
    exit 1
fi

# For non cylc-aware subprocesses that just 'exit 1' on error:
non-cylc-aware          # leave it to the trap
non-cylc-aware || {     # or handle explicitly
    cylc task failed "non-cylc-aware script failed"
    exit 1
}
# or this is OK too:
if ! non-cylc-aware; then
    cylc task failed "non-cylc-aware script failed"
    exit 1
fi

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
