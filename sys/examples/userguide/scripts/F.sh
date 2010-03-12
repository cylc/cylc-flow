#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# Task F: postprocess the storm surge model.

# UNLIKE THE OTHER TASKS IN THE USERGUIDE EXAMPLE SYSTEM, THIS ONE IS
# NOT CYLC-AWARE, SO IT HAS TO BE RUN USING THE CYLC TASK WRAPPING
# MECHANISM. 

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# check prerequisites
PRE=$TMPDIR/storm-surge-${ANALYSIS_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE
    echo "file not found: $PRE"
    exit 1
fi

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

touch $TMPDIR/storm-surge-products-${ANALYSIS_TIME}.nc
