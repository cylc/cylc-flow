#!/bin/bash

set -e  # abort on error

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/ecocontroller/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME 
#   2. $TASK_NAME 

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

VIS_TOPNET=$HOME/bin/vis_topnet

cd $HOME/running

task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

$VIS_TOPNET $REFERENCE_TIME 

task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
