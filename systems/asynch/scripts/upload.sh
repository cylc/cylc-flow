#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# check prerequisites
ONE=$CYLC_TMPDIR/products-${ASYNCID}.nc
for PRE in $ONE; do
    if [[ ! -f $PRE ]]; then
        # FAILURE MESSAGE
        cylc message -p CRITICAL "file not found: $PRE"
        cylc message --failed
        exit 1
    fi
done

# EXECUTE THE TASK ...
sleep 10

# create task outputs
cp $CYLC_TMPDIR/products-${ASYNCID}.nc $CYLC_TMPDIR/upload-${ASYNCID}.nc
cylc message "products $ASYNCID uploaded"

# SUCCESS MESSAGE
cylc message --succeeded
