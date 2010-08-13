#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM Task F IMPLEMENTATION.

# THIS TASK IS NOT CYLC-AWARE: USE THE CYLC TASK WRAPPING MECHANISM.

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
sleep $TASK_RUN_TIME_SECONDS

touch $CYLC_TMPDIR/storm-surge-products-${ANALYSIS_TIME}.nc
