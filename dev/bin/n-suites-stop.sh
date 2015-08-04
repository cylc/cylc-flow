#!/bin/bash

# Usage: $0 PREFIX
#   Stop, unregister, and delete suites registered as ${PREFIX}_$n
# Companion of start-n-suites.sh.

set -eu

PREFIX=$1

echo
for SUITE in $(cylc scan | egrep "^${PREFIX}_" | awk '{print $1}'); do
    echo $SUITE
    cylc stop --max-polls=30 --interval=2 $SUITE &
done
wait

cylc db unreg -d "^${PREFIX}_.*"
