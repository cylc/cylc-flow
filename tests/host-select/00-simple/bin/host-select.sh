#!/bin/bash
# Touch a file with current PID, should be unique for the purpose of the test
touch "${CYLC_SUITE_RUN_DIR}/$(basename "$0" '.sh')-$$"
# Just echo the host  name
echo "${CYLC_REMOTE_PLATFORM}"
exit
