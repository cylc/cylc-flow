#!/bin/bash
set -eu

echo "HELLO FROM log-check.sh shutdown handler for ${CYLC_SUITE_NAME}"

# compare events.log with the reference version
# sorted so that event order doesn't matter

sed -i 's/ (after .\+)$//' "${EVNTLOG}"
REF_LOG="${CYLC_SUITE_DEF_PATH}/events.log"

# difference with 'sort -u' (unique) because polling on timeouts may now
# result in multiple 'started' messages etc.
if ! diff -u <(sort -u "${EVNTLOG}") <(sort -u "${REF_LOG}") >&2; then 
    echo 'ERROR: event handler output logs differ' >&2
    exit 1
else
    echo 'OK: event handler output logs agree'
fi

echo "BYE FROM log-check.sh shutdown handler for ${CYLC_SUITE_NAME}"
