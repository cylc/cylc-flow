#!/bin/bash
# remove installed remote passphrase
set -e
cylc check-triggering "$@"
if [[ $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@localhost || \
      $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@$(hostname) ]]; then
    exit
fi
PPHRASE=.cylc/$CYLC_SUITE_REG_NAME/passphrase
echo -n "Removing remote passphrase ${CYLC_TEST_TASK_OWNER}@${CYLC_TEST_TASK_HOST}:$PPHRASE ... "
ssh -oBatchmode=yes ${CYLC_TEST_TASK_OWNER}@${CYLC_TEST_TASK_HOST} "rm $PPHRASE && rmdir $( dirname $PPHRASE )"
echo "Done"
