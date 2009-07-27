#!/bin/bash

set -e  # abort on error

# source sequenz environment
. $SEQUENZ_ENV

trap 'task-message CRITICAL failed' ERR

echo "WARNING: USING TEMPORARY HARDWIRED FETCH_TD INSTALLATION"
FETCH_TD=/dvel/data_dvel/fetchtd/fetchtd/src/fetchtd.py

# get streamflow data (wait till 0:15 past the hour if necessary) 

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME (=> streamflow data time)
#   2. $TASK_NAME
#   3. $SEQUENZ_ENV

# INTENDED USER:
# * hydrology_(dvel|test|oper)

task-message NORMAL started

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
    task-message CRITICAL failed
	exit 1
fi
STREAMFLOW_TIME=$REFERENCE_TIME

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
    task-message CRITICAL failed
	exit 1
fi

# LAUNCH TOPNET NOW

INPUT_DIR=$HOME/input/topnet

NOW_epochseconds=$(date +%s)

CUTOFF_YYYYMMDDHHmm=${STREAMFLOW_TIME}15  # 15 min past the streamflow data hour
YYYYMMDD=${CUTOFF_YYYYMMDDHHmm%????}
HHmm=${CUTOFF_YYYYMMDDHHmm#????????}
CUTOFF_epochseconds=$(date --date="$YYYYMMDD $HHmm" +%s)

cd $HOME/running

# check current time and wait for the streamflow cutoff if necessary
if (( NOW_epochseconds >= CUTOFF_epochseconds )); then
    task-message NORMAL "CATCHINGUP: data already available for $STREAMFLOW_TIME"
else
    # compute seconds to wait until cutoff
    WAIT_seconds=$(( CUTOFF_epochseconds - NOW_epochseconds ))
    WAIT_minutes=$(( WAIT_seconds / 60 ))
    task-message NORMAL "CAUGHTUP: waiting till $YYYYMMDD ${HHmm%??}:${HHmm#??} for $STREAMFLOW_TIME"
    sleep $WAIT_seconds
fi

# get the streamflow data
# TDSERVER FREQUENTLY FAILS TO RETURN A FILE, SO DO MULTIPLE RETRIES
MAX_ATTEMPTS=10

STREAMFLOW_DATA=/dvel/data_dvel/output/td2cf/streamobs_${STREAMFLOW_TIME}_utc_ods_nz.nc
if [[ -f $STREAMFLOW_DATA ]]; then
    task-message NORMAL "streamflow data already exists for $STREAMFLOW_TIME"
else
    # fetch_td returns when the data file arrives, or it times out
    ATTEMPT=0
    TRY_AGAIN=true
    set +e  # DONT ABORT ON ERROR HERE (retry in case of failure)
    trap - ERR
    while $TRY_AGAIN; do
        ATTEMPT=$(( ATTEMPT + 1 ))
        task-message NORMAL "starting streamflow data extraction for ${STREAMFLOW_TIME}, attempt $ATTEMPT"
        python $FETCH_TD
        if [[ $? != 0 || ! -f $STREAMFLOW_DATA ]]; then
            if (( ATTEMPT < MAX_ATTEMPTS )); then
                task-message WARNING "streamflow data retrieval FAILED, attempt $ATTEMPT"
            else
                task-message CRITICAL "streamflow data retrieval FAILED ALL $MAX_ATTEMPTS ATTEMPTS"
                task-message CRITICAL failed
                exit 1
            fi
        else
            TRY_AGAIN=false
        fi
    done
fi

# reset error trapping
set -e  # abort on error
trap 'task-message CRITICAL failed' ERR

task-message NORMAL "got $STREAMFLOW_DATA"
task-message NORMAL "got streamflow data for $STREAMFLOW_TIME"

# copy streamflow data to my input dir

if [[ ! -d $INPUT_DIR ]]; then
    mkdir -p $INPUT_DIR
fi
cp $STREAMFLOW_DATA $INPUT_DIR

task-message NORMAL finished
