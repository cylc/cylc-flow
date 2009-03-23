#!/bin/bash

set -e  # abort on error

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/sequenz/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME    e.g. 2008102018
#   2. $TASK_NAME         e.g. topnet_and_vis
#   3. $MODEL_NAME        e.g. topnet

# runs create_images.sh in /$HOME/running/$MODEL/product

if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $MODEL_NAME ]]; then
	task_message CRITICAL "MODEL_NAME not defined"
	exit 1
fi


SYSTEM=${USER##*_}
SCRIPT=/$SYSTEM/ecoconnect_$SYSTEM/bin/create_images.sh
cd $HOME/running/$MODEL_NAME/product

task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

$SCRIPT

task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
