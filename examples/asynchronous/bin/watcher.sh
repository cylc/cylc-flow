#!/bin/bash

COUNT=0
while true; do
    rnd=$RANDOM  # ($RANDOM is a bash builtin)
    let "rnd %= 10"  # random number less than 10
    sleep $(( rnd + 5 ))  # random seconds between 5 and 15
    cylc task message "SATID-${COUNT} ready for processing"
    COUNT=$(( COUNT + 1 ))
done
