#!/bin/bash
set -e
if [[ $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@localhost || \
      $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@$(hostname) ]]; then
    exit
fi
PPHRASE=$CYLC_SUITE_DEF_PATH/passphrase
# copy the passphrase over in case this host does not use ssh messaging
echo "Copying suite passphrase to ${CYLC_TEST_TASK_OWNER}@$CYLC_TEST_TASK_HOST"
DEST=.cylc/$CYLC_SUITE_REG_NAME
ssh -oBatchmode=yes ${CYLC_TEST_TASK_OWNER}@$CYLC_TEST_TASK_HOST mkdir -p $DEST
scp -oBatchmode=yes $PPHRASE ${CYLC_TEST_TASK_OWNER}@${CYLC_TEST_TASK_HOST}:$DEST/
echo "Done"
