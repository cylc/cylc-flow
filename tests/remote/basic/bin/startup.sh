#!/bin/bash
set -e
OWNER=$CYLC_TEST_TASK_OWNER
HOST=$CYLC_TEST_TASK_HOST
PPHRASE=$CYLC_SUITE_DEF_PATH/passphrase
if [[ -z $OWNER ]]; then 
    echo "ERROR: \$CYLC_TEST_TASK_OWNER is not defined"
    exit 1
elif [[ -z $HOST ]]; then
    echo "ERROR: \$CYLC_TEST_TASK_HOST is not defined"
    exit 1
fi
if [[ $OWNER@$HOST == $USER@localhost || $OWNER@$HOST == $USER@$(hostname) ]]; then
    exit
fi
# copy the passphrase over in case this host does not use ssh messaging
echo "Copying suite passphrase to ${OWNER}@$HOST"
DEST=.cylc/$CYLC_SUITE_REG_NAME
ssh -oBatchmode=yes ${OWNER}@$HOST mkdir -p $DEST
scp -oBatchmode=yes $PPHRASE ${OWNER}@${HOST}:$DEST/
echo "Done"
