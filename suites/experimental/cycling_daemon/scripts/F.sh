#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# Task F: postprocess the storm surge model.

# THIS TASK IS NOT CYLC-AWARE, SO IT HAS TO BE RUN USING THE CYLC TASK
# WRAPPING MECHANISM. 

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# check environment
check-env.sh || exit 1

echo
for ARG in $@; do
    echo commandline: $ARG
done
echo

# check prerequisites
PRE=$CYLC_TMPDIR/storm-surge-${ANALYSIS_TIME}.nc
if [[ ! -f $PRE ]]; then
    # FAILURE
    echo "file not found: $PRE"
    exit 1
fi

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

touch $CYLC_TMPDIR/storm-surge-products-${ANALYSIS_TIME}.nc
