#!/bin/bash

set -e  # abort on error

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/ecocontroller/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

echo "WARNING: USING TEMPORARY HARDWIRED FETCH_TD INSTALLATION"
FETCH_TD=/dvel/data_dvel/fetchtd/fetchtd/src/fetchtd.py

# get streamflow data (wait till 0:15 past the hour if necessary) and
# launch the topnet model

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TN_FILENAME (tn netcdf file from most recenet nzlam post processing)

# INTENDED USER:
# * hydrology_(dvel|test|oper)

if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $TN_FILENAME ]]; then
    task_message CRITICAL "TN_FILENAME not defined"
    exit 1
fi

NOW=$(date "+%Y%m%d%H%M")
STREAMFLOW_CUTOFF=${REFERENCE_TIME}15  # 15 min past the hour

# check current time and wait for the streamflow cutoff if necessary
if (( NOW >= STREAMFLOW_CUTOFF )); then
    task_message NORMAL "CATCHUP: streamflow data already available for $REFERENCE_TIME"
else
    task_message NORMAL "UPTODATE: waiting for streamflow data for $REFERENCE_TIME"

    while true; do
        # TO DO: CALCULATE THE CORRECT WAIT TIME INSTEAD OF POLLING LIKE A 'TARD
        sleep 60
        NOW=$(date "+%Y%m%d%H%M")
        if (( NOW >= STREAMFLOW_CUTOFF )); then
            break
        fi
    done
fi

# get the streamflow data
task_message NORMAL "streamflow extraction started for $REFERENCE_TIME"
STREAMFLOW_DATA=/dvel/data_dvel/streamq_${REFERENCE_TIME}_utc_ods_nz.nc
python $FETCH_TD

if [[ $? != 0 || ! -f $STREAMFLOW_DATA ]]; then
    task_message CRITICAL "Failed to get streamflow data"
    exit 1
fi
task_message NORMAL "Got $STREAMFLOW_DATA"
task_message NORMAL "got streamflow data for $REFERENCE_TIME"

# LAUNCH TOPNET NOW
task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

task_message NORMAL "using $TN_FILENAME"

task_message CRITICAL "TOPNET DISABLED!"

task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
