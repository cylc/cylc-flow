#!/bin/bash

set -eu

# Watch for a file to appear (indefinitely -  run with the 'timeout' command).

FILE=$1

while true; do
    [[ -e $FILE ]] && exit 0
    sleep 1
done
