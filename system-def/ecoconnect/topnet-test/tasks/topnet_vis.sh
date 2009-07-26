#!/bin/bash

set -e  # abort on error

trap 'task-message CRITICAL "$TASK_NAME failed"' ERR

# source sequenz environment
. $SEQUENZ_ENV

# Run topnet visualisation.

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME
#   3. $NZLAM_AGE ('old' or 'new': new nzlam input or not)
#   5. $SEQUENZ_ENV

# INTENDED USER:
# * hydrology_(dvel|test|oper)

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
    task-message CRITICAL "$TASK_NAME failed"
	exit 1
fi
STREAMFLOW_TIME=$REFERENCE_TIME

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
    task-message CRITICAL "$TASK_NAME failed"
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

VIS_TOPNET_SSF=$HOME/bin/vis_topnet_ssf
VIS_TOPNET=$HOME/bin/vis_topnet
cd $HOME/running

if [[ $NZLAM_AGE == old ]]; then
    task-message NORMAL "ssf only ($NZLAM_AGE nzlam)"
    $VIS_TOPNET_SSF $REFERENCE_TIME 

elif [[ $NZLAM_AGE == new ]]; then
    task-message NORMAL "ssf and rrf ($NZLAM_AGE nzlam)"
    $VIS_TOPNET $REFERENCE_TIME 

else
    task-message CRITICAL "unknown \$NZLAM_AGE"
    task-message CRITICAL "$TASK_NAME failed"
    exit 1
fi

task-message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
