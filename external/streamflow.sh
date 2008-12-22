#!/bin/bash

set -e  # abort on error
set -x

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/sequenz/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

echo "WARNING: USING TEMPORARY HARDWIRED FETCH_TD INSTALLATION"
FETCH_TD=/dvel/data_dvel/fetchtd/fetchtd/src/fetchtd.py

# get streamflow data (wait till 0:15 past the hour if necessary) 

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME (=> streamflow data time)
#   2. $TASK_NAME

# INTENDED USER:
# * hydrology_(dvel|test|oper)

if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi
STREAMFLOW_TIME=$REFERENCE_TIME

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

# LAUNCH TOPNET NOW
task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

INPUT_DIR=$HOME/input/topnet

NOW=$(date "+%Y%m%d%H%M")
STREAMFLOW_CUTOFF=${STREAMFLOW_TIME}15  # 15 min past the hour

cd $HOME/running

# check current time and wait for the streamflow cutoff if necessary
if (( NOW >= STREAMFLOW_CUTOFF )); then
    task_message NORMAL "CATCHUP: data already available for $STREAMFLOW_TIME"
else
    task_message NORMAL "UPTODATE: waiting on data for $STREAMFLOW_TIME"

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
task_message NORMAL "streamflow extraction started for $STREAMFLOW_TIME"
STREAMFLOW_DATA=/dvel/data_dvel/streamq_${STREAMFLOW_TIME}_utc_ods_nz.nc
python $FETCH_TD

if [[ $? != 0 || ! -f $STREAMFLOW_DATA ]]; then
    task_message CRITICAL "Failed to get streamflow data"
    exit 1
fi
task_message NORMAL "got $STREAMFLOW_DATA"
task_message NORMAL "got streamflow data for $STREAMFLOW_TIME"

# copy streamflow data to my input dir

if [[ ! -d $INPUT_DIR ]]; then
    mkdir -p $INPUT_DIR
fi
cp $STREAMFLOW_DATA $INPUT_DIR

task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
