#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SUITE. 
# oneoff startup task to clean out the suite work space.

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

if [[ -z $CYLC_TMPDIR ]]; then
    cylc task-failed "\$CYLC_TMPDIR must be defined in suite_config.py for this suite"
    exit 1
fi

mkdir -p $CYLC_TMPDIR || \
{
    cylc task-failed "failed to create $CYLC_TMPDIR"
    exit 1
}

# register the userguide sub-suite
# (this is ok if already registered)
cylc register $CYLC_DIR/suites/userguide userguide

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

echo "CLEANING $CYLC_TMPDIR"
rm -rf $CYLC_TMPDIR/* || \
{
    cylc task-failed "failed to clean out $CYLC_TMPDIR"
    exit 1
}

# SUCCESS MESSAGE
cylc task-finished
