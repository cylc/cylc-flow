#!/bin/bash

set -e  # abort on error

trap 'task-message CRITICAL "$TASK_NAME failed"' ERR

# source sequenz environment
. $SEQUENZ_ENV

# Run the topnet model. The streamflow task must run before this task.

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME
#   3. $NZLAM_TIME (time of the tn_ netcdf file to use as input)
#   4. $SEQUENZ_ENV

# INTENDED USER:
# * hydrology_(dvel|test|oper)

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi
STREAMFLOW_TIME=$REFERENCE_TIME

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $NZLAM_TIME ]]; then
    task-message CRITICAL "NZLAM_TIME not defined"
    exit 1
fi

INPUT_DIR=$HOME/input/topnet
RUN_TOPNET=$HOME/bin/run_topnet.sh

# BASIN IDS:
CLUTHA=14070121
RANGITAIKI=04029020
WAIRAU=11016543

cd $HOME/running

task-message NORMAL "$TASK_NAME started for $REFERENCE_TIME"
task-message NORMAL "(nzlam time ${NZLAM_TIME})"

task-message WARNING "Running TopNet on Rangataiki basin only"
for BASIN in $RANGITAIKI; do
    task-message NORMAL "processing basin $BASIN"
    task-message NORMAL "$RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN"
    $RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN
    echo TOPNET RETURNED $?
    echo $PWD
done

task-message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
