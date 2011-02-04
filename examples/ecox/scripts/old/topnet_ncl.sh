#!/bin/bash

# Run topnet visualisation.

# Task-specific input:
#   $NZLAM_AGE ('old' or 'new': new nzlam input or not)

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

INPUT_DIR=$HOME/input/topnet
RUN_TOPNET=$HOME/bin/run_topnet.sh

# BASIN IDS:
CLUTHA=14070121
RANGITAIKI=04029020
WAIRAU=11016543

cd $HOME/running

VIS_TOPNET_SSF=$HOME/bin/vis_topnet_ssf
VIS_TOPNET=$HOME/bin/vis_topnet
cd $HOME/running

if [[ $NZLAM_AGE == old ]]; then
    cylc message "ssf only ($NZLAM_AGE nzlam)"
    $VIS_TOPNET_SSF $CYCLE_TIME 

elif [[ $NZLAM_AGE == new ]]; then
    cylc message "ssf and rrf ($NZLAM_AGE nzlam)"
    $VIS_TOPNET $CYCLE_TIME 

else
    cylc message -p CRITICAL "unknown \$NZLAM_AGE"
    cylc message --failed
    exit 1
fi

cylc message --succeeded
