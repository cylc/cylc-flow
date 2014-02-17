#!/bin/bash
set -e
PPHRASE=$CYLC_SUITE_DEF_PATH/passphrase
if [[ $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@localhost || $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@$(hostname) ]]; then
    exit
fi
# copy the passphrase over in case this host does not use ssh messaging
echo "Copying suite passphrase to ${CYLC_TEST_TASK_OWNER}@$CYLC_TEST_TASK_HOST"
DEST=.cylc/$CYLC_SUITE_REG_NAME
ssh -oBatchmode=yes ${CYLC_TEST_TASK_OWNER}@$CYLC_TEST_TASK_HOST mkdir -p $DEST
scp -oBatchmode=yes $PPHRASE ${CYLC_TEST_TASK_OWNER}@${CYLC_TEST_TASK_HOST}:$DEST/
echo "Done"
