#!/bin/bash

# THIS IS A CYLC TASK SCRIPT TEMPLATE FOR THE 'FREE' TASK TYPE, I.E.
# NON-FORECAST MODEL TASKS THAT HAVE NO PREVIOUS-INSTANCE DEPENDENCE.

# START MESSAGE
cylc message --started

# CHECK TASK PREREQUISITES
# For example, set $PREREQUISITES to a list of $CYCLE_TIME dependent
# input files then: 
for FILE in $PREREQUISITES; do
    if [[ ! -f $FILE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE GUTS OF THE TASK:

# (1) to call an external script or executable that generates task outputs:
if ! $EXTERNAL; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "file not found: $PRE"
    cylc message --failed
    exit 1
fi

# IF possible the aforementioned external script or executable should
# report completion of task outputs as it goes, as in (2) below.

# IF it does NOT report completion of task outputs as it goes, do so now
cycl message --all-outputs-completed
# OR send each output message explicitly as in (2) below.

# (2) for outputs scripted in this file, report each completed as we go:
# {CODE: COMPLETE A REGISTERED TASK OUTPUT}
cylc message "foo files ready for $CYCLE_TIME"

# FINISHED MESSAGE
cylc message --succeeded
