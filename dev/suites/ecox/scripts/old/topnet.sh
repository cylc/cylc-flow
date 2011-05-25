#!/bin/bash

# Run the topnet model. The streamflow task must run before this task.

# Task-specific input:
#   $NZLAM_TIME (time of the tn_ netcdf file to use as input)

# INTENDED USER:
# * hydrology_(dvel|test|oper)

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

if [[ -z $CYCLE_TIME ]]; then
	cylc message -p CRITICAL "CYCLE_TIME not defined"
    cylc message --failed
	exit 1
fi
STREAMFLOW_TIME=$CYCLE_TIME

if [[ -z $TASK_NAME ]]; then
	cylc message -p CRITICAL "TASK_NAME not defined"
    cylc message --failed
	exit 1
fi

if [[ -z $NZLAM_TIME ]]; then
    cylc message -p CRITICAL "NZLAM_TIME not defined"
    cylc message --failed
    exit 1
fi

INPUT_DIR=$HOME/input/topnet
RUN_TOPNET=$HOME/bin/run_topnet.sh

# BASIN IDS:
CLUTHA=14070121
RANGITAIKI=04029020
WAIRAU=11016543

cd $HOME/running

cylc message "(nzlam time ${NZLAM_TIME})"

cylc message -p WARNING "Running TopNet on Rangataiki basin only"
for BASIN in $RANGITAIKI; do
    cylc message "processing basin $BASIN"
    cylc message "$RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN"
    $RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN
    echo TOPNET RETURNED $?
    echo $PWD
done

cylc message --all-outputs-completed
cylc message --succeeded
