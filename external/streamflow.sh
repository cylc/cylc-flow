#!/bin/bash

set -e  # abort on error

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

NOW_epochseconds=$(date +%s)

CUTOFF_YYYYMMDDHHmm=${STREAMFLOW_TIME}15  # 15 min past the streamflow data hour
YYYYMMDD=${CUTOFF_YYYYMMDDHHmm%????}
HHmm=${CUTOFF_YYYYMMDDHHmm#????????}
CUTOFF_epochseconds=$(date --date="$YYYYMMDD $HHmm" +%s)

cd $HOME/running

# check current time and wait for the streamflow cutoff if necessary
if (( NOW_epochseconds >= CUTOFF_epochseconds )); then
    task_message NORMAL "CATCHINGUP: data already available for $STREAMFLOW_TIME"
else
    # compute seconds to wait until cutoff
    WAIT_seconds=$(( CUTOFF_epochseconds - NOW_epochseconds ))
    WAIT_minutes=$(( WAIT_seconds / 60 ))
    #task_message NORMAL "CAUGHTUP: waiting for  $WAIT_minutes min for streamflow data"
    task_message NORMAL "CAUGHTUP: waiting till $YYYYMMDD ${HHmm%??}:${HHmm#??} for new streamflow data "
    sleep $WAIT_seconds
fi

# get the streamflow data
# TDSERVER FREQUENTLY FAILS TO RETURN A FILE, SO DO MULTIPLE RETRIES
MAX_ATTEMPTS=10

STREAMFLOW_DATA=/dvel/data_dvel/output/td2cf/streamq_${STREAMFLOW_TIME}_utc_ods_nz.nc
if [[ -f $STREAMFLOW_DATA ]]; then
    task_message NORMAL "streamflow data already exists for $STREAMFLOW_TIME"
else
    # fetch_td returns when the data file arrives, or it times out
    ATTEMPT=0
    TRY_AGAIN=true
    set +e  # DONT ABORT ON ERROR HERE (retry in case of failure)
    trap - ERR
    while $TRY_AGAIN; do
        ATTEMPT=$(( ATTEMPT + 1 ))
        task_message NORMAL "streamflow data extraction started for ${STREAMFLOW_TIME}, attempt $ATTEMPT"
        python $FETCH_TD
        if [[ $? != 0 || ! -f $STREAMFLOW_DATA ]]; then
            if (( ATTEMPT < MAX_ATTEMPTS )); then
                task_message WARNING "streamflow data retrieval FAILED, attempt $ATTEMPT"
            else
                task_message CRITICAL "streamflow data retrieval FAILED ALL $MAX_ATTEMPTS ATTEMPTS"
                task_message CRITICAL "$TASK_NAME failed"
                exit 1
            fi
        else
            TRY_AGAIN=false
        fi
    done
fi

set -e  # abort on error
trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

task_message NORMAL "got $STREAMFLOW_DATA"
task_message NORMAL "got streamflow data for $STREAMFLOW_TIME"

# copy streamflow data to my input dir

if [[ ! -d $INPUT_DIR ]]; then
    mkdir -p $INPUT_DIR
fi
cp $STREAMFLOW_DATA $INPUT_DIR

task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
