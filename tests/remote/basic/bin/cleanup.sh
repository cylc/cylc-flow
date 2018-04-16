#!/bin/bash
# remove installed remote passphrase
set -e
cylc check-triggering "$@"
if [[ $CYLC_TEST_OWNER@$CYLC_TEST_HOST == $USER@localhost || \
      $CYLC_TEST_OWNER@$CYLC_TEST_HOST == $USER@$(hostname) ]]; then
    exit
fi
echo "Done"
