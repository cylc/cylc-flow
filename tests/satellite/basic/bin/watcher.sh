#!/bin/bash

N_PASSES=${N_PASSES:-10}
SLEEP_MIN=${SLEEP_MIN:-5}
SLEEP_MAX=${SLEEP_MAX:-15}

(( SLEEP_DIFF = SLEEP_MAX - SLEEP_MIN ))

COUNT=0
while (( COUNT < N_PASSES )); do
    rnd=$RANDOM  # ($RANDOM is a bash builtin)
    let "rnd %= $SLEEP_DIFF"  # e.g. a random number less than 10
    cylc task message "SatID-$RANDOM ready for processing"
    sleep $(( $SLEEP_MIN + rnd ))  # e.g. sleep between 5 and 15 seconds
    (( COUNT+=1 ))
done

# stop the suite when done (there'll be waiting downstream tasks)
sleep 2 # let the final downstream tasks trigger
cylc stop $CYLC_SUITE_NAME

