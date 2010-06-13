#!/bin/bash

cylc message --started

COUNT=0

PLATFORM=$( uname -n )

while (( COUNT < 10 )); do
    cylc message "$COUNT - hello from $PLATFORM"
    COUNT=$(( COUNT + 1 ))
    sleep 1
done

cylc message "remote platform processing completed for $CYCLE_TIME"
cylc message --succeeded
