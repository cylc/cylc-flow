#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM startup task IMPLEMENTATION.
# (cleans out the system work space).

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

if [[ -z $CYLC_TMPDIR ]]; then
    cylc task-failed "\$CYLC_TMPDIR must be defined in system_config.py for this system"
    exit 1
fi
sleep 5

mkdir -p $CYLC_TMPDIR || \
{
    cylc task-failed "failed to create $CYLC_TMPDIR"
    exit 1
}
# make world-writeable so we can test a multi-owner system.
chmod go+rxw $CYLC_TMPDIR

# EXECUTE THE TASK ...
sleep $TASK_RUN_TIME_SECONDS

echo "CLEANING $CYLC_TMPDIR"
rm -rf $CYLC_TMPDIR/* || \
{
    cylc task-failed "failed to clean out $CYLC_TMPDIR"
    exit 1
}

# SUCCESS MESSAGE
cylc task-finished
