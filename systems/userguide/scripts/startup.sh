#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# CYLC USERGUIDE EXAMPLE SYSTEM. 
# oneoff startup task to clean out the system work space.

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

mkdir -p $TMPDIR || \
{
    cylc message -p CRITICAL "failed to create $TMPDIR"
    cylc message --failed
    exit 1
}

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

echo "CLEANING $TMPDIR"
rm -rf $TMPDIR/* || \
{
    cylc message -p CRITICAL "failed to clean out $TMPDIR"
    cylc message --failed
    exit 1
}

# SUCCESS MESSAGE
cylc message --succeeded
