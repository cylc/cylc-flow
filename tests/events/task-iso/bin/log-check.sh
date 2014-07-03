#!/bin/bash

echo "HELLO FROM log-check.sh shutdown handler for $CYLC_SUITE_REG_NAME"

# compare events.log with the reference version
# sorted so that event order doesn't matter

NEW_LOG=$EVNTLOG
REF_LOG=$CYLC_SUITE_DEF_PATH/events.log

# difference with 'sort -u' (unique) because polling on timeouts may now
# result in multiple 'started' messages etc.
if ! diff <(sort -u $NEW_LOG) <(sort -u $REF_LOG); then 
    echo "ERROR: event handler output logs differ" >&2
    diff <(sort -u $NEW_LOG) <(sort -u $REF_LOG) >&2
    exit 1
else
    echo "OK: event handler output logs agree"
fi

echo "BYE FROM log-check.sh shutdown handler for $CYLC_SUITE_REG_NAME"

