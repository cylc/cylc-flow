#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task F: postprocess the storm surge model.
# THIS TASK DOES NO MESSAGING (AND IS IN FACT ENTIRELY UNAWARE OF CYLC),
# TO ILLUSTRATE THE USE OF CYLC'S TASK WRAPPING MECHANISM.

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# check prerequistes
PRE=$TMPDIR/storm-surge-${ANALYSIS_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE
    echo "file note found: $PRE"
    exit 1
fi

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

touch $TMPDIR/storm-surge-products-${ANALYSIS_TIME}.nc
