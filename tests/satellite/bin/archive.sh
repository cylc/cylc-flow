#!/bin/bash

# "archive" satellite data detected by the watcher task

set -e
cylc util checkvars ASYNCID

cylc task message "Archiving data $ASYNCID"

#sleep 10
cylc task message "$ASYNCID archived"
