#!/bin/bash

set -e  # abort on error

# source sequenz environment
. $SEQUENZ_ENV

trap 'task-message CRITICAL failed' ERR

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME    e.g. 2008102018
#   2. $TASK_NAME         e.g. topnet_and_vis
#   3. $MODEL_NAME        e.g. topnet
#   4. $SEQUENZ_ENV

# runs create_images.sh in /$HOME/running/$MODEL/product

task-message NORMAL started

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $MODEL_NAME ]]; then
	task-message CRITICAL "MODEL_NAME not defined"
    task-message CRITICAL failed
	exit 1
fi

SYSTEM=${USER##*_}
SCRIPT=/$SYSTEM/ecoconnect_$SYSTEM/bin/create_images.sh
cd $HOME/running/$MODEL_NAME/product

$SCRIPT

task-message NORMAL finished
