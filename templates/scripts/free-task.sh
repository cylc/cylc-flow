#!/bin/bash

# THIS IS A CYLC TASK SCRIPT TEMPLATE FOR THE 'FREE' TASK TYPE, I.E.
# NON-FORECAST MODEL TASKS THAT HAVE NO PREVIOUS-INSTANCE DEPENDENCE.

# TASK STARTED
cylc message --started

# CHECK TASK PREREQUISITES
# {CODE: define $CYCLE_TIME dependent input files in $PREREQUISITES}
for PRE in $PREREQUISITES; do
    if [[ ! -f $PRE ]]; then
        # TASK FAILED
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# NOW EXECUTE THE GUTS OF THE TASK:
# -- (1) call an EXTERNAL SCRIPT OR EXECUTABLE that generates task outputs:
if ! $EXTERNAL; then
    # TASK FAILED
    cylc message -p CRITICAL "Error in $EXTERNAL"
    cylc message --failed
    exit 1
fi
# -- IF $EXTERNAL does NOT report outputs as it goes, do it now en masse:
cycl message --all-outputs-completed

# -- OR (2) for outputs scripted in this file, report as we go:
   # {CODE: COMPLETE A REGISTERED TASK OUTPUT}
cylc message "foo files ready for $CYCLE_TIME"
   # {CODE: COMPLETE ANOTHER REGISTERED TASK OUTPUT}
cylc message "bar data processing done for $CYCLE_TIME"

# TASK FINISHED
cylc message --succeeded
