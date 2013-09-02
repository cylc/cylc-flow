#!/bin/bash
# remove installed remote passphrase
set -e
OWNER=$CYLC_TEST_TASK_OWNER
HOST=$CYLC_TEST_TASK_HOST
if [[ -z $OWNER ]]; then 
    echo "ERROR: \$CYLC_TEST_TASK_OWNER is not defined"
    exit 1
elif [[ -z $HOST ]]; then
    echo "ERROR: \$CYLC_TEST_TASK_HOST is not defined"
    exit 1
fi
PPHRASE=.cylc/$CYLC_SUITE_REG_NAME/passphrase
echo -n "Removing remote passphrase ${OWNER}@${HOST}:$PPHRASE ... "
ssh -oBatchmode=yes ${OWNER}@${HOST} "rm $PPHRASE && rmdir $( dirname $PPHRASE )"
echo "Done"

