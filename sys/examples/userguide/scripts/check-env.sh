#!/bin/bash

# CHECK ENVIRONMENT

if [[ -z $REAL_TIME_ACCEL_X ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "REAL_TIME_ACCEL not defined"
    cylc message --failed
    exit 1
fi

if [[ -z $TMPDIR ]]; then
    # FAILURE MESSAGE
    cylc message -p CRITICAL "TMPDIR not defined"
    cylc message --failed
    exit 1
fi
