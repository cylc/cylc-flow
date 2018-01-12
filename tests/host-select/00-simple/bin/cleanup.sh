#!/bin/bash
# remove installed remote passphrase
set -e
cylc check-triggering "$@"
if [[ $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@localhost || \
      $CYLC_TEST_TASK_OWNER@$CYLC_TEST_TASK_HOST == $USER@$(hostname) ]]; then
    exit
fi
echo "Done"
