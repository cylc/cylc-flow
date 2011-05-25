#!/bin/bash

# get streamflow data 

echo "WARNING: USING TEMPORARY HARDWIRED FETCH_TD INSTALLATION"
FETCH_TD=/dvel/data_dvel/fetchtd/fetchtd/src/fetchtd.py

# INPUT:
# standard cylc environment

# INTENDED USER:
# * hydrology_(dvel|test|oper)

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

STREAMFLOW_TIME=$CYCLE_TIME

INPUT_DIR=$HOME/input/topnet

NOW_epochseconds=$(date +%s)

CUTOFF_YYYYMMDDHHmm=${STREAMFLOW_TIME}15  # 15 min past the streamflow data hour
YYYYMMDD=${CUTOFF_YYYYMMDDHHmm%????}
HHmm=${CUTOFF_YYYYMMDDHHmm#????????}
CUTOFF_epochseconds=$(date --date="$YYYYMMDD $HHmm" +%s)

cd $HOME/running

# get the streamflow data
# TDSERVER FREQUENTLY FAILS TO RETURN A FILE, SO DO MULTIPLE RETRIES
MAX_ATTEMPTS=10

STREAMFLOW_DATA=/dvel/data_dvel/output/td2cf/streamobs_${STREAMFLOW_TIME}_utc_ods_nz.nc
if [[ -f $STREAMFLOW_DATA ]]; then
    cylc message "streamflow data already exists for $STREAMFLOW_TIME"
else
    # fetch_td returns when the data file arrives, or it times out
    ATTEMPT=0
    TRY_AGAIN=true
    set +e  # DONT ABORT ON ERROR HERE (retry in case of failure)
    trap - ERR
    while $TRY_AGAIN; do
        ATTEMPT=$(( ATTEMPT + 1 ))
        cylc message "starting streamflow data extraction for ${STREAMFLOW_TIME}, attempt $ATTEMPT"
        python $FETCH_TD
        if [[ $? != 0 || ! -f $STREAMFLOW_DATA ]]; then
            if (( ATTEMPT < MAX_ATTEMPTS )); then
                cylc message -p WARNING "streamflow data retrieval FAILED, attempt $ATTEMPT"
            else
                cylc message -p CRITICAL "streamflow data retrieval FAILED ALL $MAX_ATTEMPTS ATTEMPTS"
                cylc message --failed
                exit 1
            fi
        else
            TRY_AGAIN=false
        fi
    done
fi

# reset error trapping
set -e; trap 'cylc message --failed' ERR

cylc message "got $STREAMFLOW_DATA"
cylc message "got streamflow data for $STREAMFLOW_TIME"

# copy streamflow data to my input dir
if [[ ! -d $INPUT_DIR ]]; then
    mkdir -p $INPUT_DIR
fi
cp $STREAMFLOW_DATA $INPUT_DIR

cylc message --succeeded
