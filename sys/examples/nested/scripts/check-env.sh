#!/bin/bash

# CHECK ENVIRONMENT

if [[ -z $REAL_TIME_ACCEL ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$REAL_TIME_ACCEL is not defined"
    cylc message --failed
    exit 1
fi

if [[ -z $TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "\$TMPDIR is not defined"
    cylc message --failed
    exit 1
fi
