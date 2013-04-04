#!/bin/bash

echo "HELLO FROM log-check.sh shutdown handler for $CYLC_SUITE_REG_NAME"
LOG=$CYLC_SUITE_LOG_DIR/log

EVENTS="submitted submission_timeout started execution_timeout warning succeeded"
FAIL=false
for EVENT in $EVENTS; do
    if ! grep "Queueing $EVENT event handler" $LOG > /dev/null; then
        echo "ERROR: event $EVENT not logged"
        FAIL=true
    fi
done

if $FAIL; then
    echo "ERROR: one or more event handlers not called"
    exit 1
fi
echo "OK: all expected event handlers called"

echo "BYE FROM log-check.sh shutdown handler for $CYLC_SUITE_REG_NAME"

