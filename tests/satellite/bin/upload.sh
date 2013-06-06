#!/bin/bash

# "upload" satellite data detected by the watcher task

set -e
cylc util checkvars ASYNCID

cylc task message "Uploading data $ASYNCID"

#sleep 10
cylc task message "$ASYNCID uploaded"
