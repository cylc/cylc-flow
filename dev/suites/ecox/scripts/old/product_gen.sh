#!/bin/bash

# Task-specific inputs: 
#  $MODEL_NAME

# runs create_images.sh in /$HOME/running/$MODEL/product

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

if [[ -z $CYCLE_TIME ]]; then
	cylc message -p CRITICAL "CYCLE_TIME not defined"
    cylc message --failed
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	cylc message -p CRITICAL "TASK_NAME not defined"
    cylc message --failed
	exit 1
fi

if [[ -z $MODEL_NAME ]]; then
	cylc message -p CRITICAL "MODEL_NAME not defined"
    cylc message --failed
	exit 1
fi

SYSTEM=${USER##*_}
SCRIPT=/$SYSTEM/ecoconnect_$SYSTEM/bin/create_images.sh
cd $HOME/running/$MODEL_NAME/product

if $SCRIPT; then
    cylc message --all-outputs-completed
    cylc message --succeeded
else
    cylc message --failed
