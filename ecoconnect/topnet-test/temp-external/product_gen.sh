#!/bin/bash

set -e  # abort on error

. /test/ecoconnect_test/sequenz/bin/environment.sh

trap 'task-message CRITICAL "$TASK_NAME failed"' ERR

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME    e.g. 2008102018
#   2. $TASK_NAME         e.g. topnet_and_vis
#   3. $MODEL_NAME        e.g. topnet

# runs create_images.sh in /$HOME/running/$MODEL/product

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $MODEL_NAME ]]; then
	task-message CRITICAL "MODEL_NAME not defined"
	exit 1
fi


SYSTEM=${USER##*_}
SCRIPT=/$SYSTEM/ecoconnect_$SYSTEM/bin/create_images.sh
cd $HOME/running/$MODEL_NAME/product

task-message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

$SCRIPT

task-message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
