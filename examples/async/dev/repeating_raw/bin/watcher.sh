#!/bin/bash

# This script runs indefinitely and reports arrival of 
# imaginary satellite data at random intervals of between
# 5 and 15 seconds. Each pass is identified by a random 
# identifier that starts with "SATID-".

while true; do
    rnd=$RANDOM  # ($RANDOM is a bash builtin)
    let "rnd %= 10"  # a random number less than 10
    sleep $(( rnd + 5 ))  # sleep between 5 and 15 seconds
    cylc task message "SATID-$RANDOM ready for processing"
done
