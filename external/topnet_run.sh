#!/bin/bash

set -e  # abort on error

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/ecocontroller/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

echo "WARNING: USING TEMPORARY HARDWIRED FETCH_TD INSTALLATION"
FETCH_TD=/dvel/data_dvel/fetchtd/fetchtd/src/fetchtd.py

# run the topnet model AND visualisation (see task_class.py for 
# why we combine the two tasks in the case of topnet only).

# streamflow data extraction must run before this task

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME
#   3. $NZLAM_TIME (time of the tn_ netcdf file to use as input)
#   4. $NZLAM_AGE ('old' or 'new': new nzlam input or not)

# INTENDED USER:
# * hydrology_(dvel|test|oper)

if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi
STREAMFLOW_TIME=$REFERENCE_TIME

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

if [[ -z $NZLAM_TIME ]]; then
    task_message CRITICAL "NZLAM_TIME not defined"
    exit 1
fi

INPUT_DIR=$HOME/input/topnet
RUN_TOPNET=$HOME/bin/run_topnet.sh

# BASIN IDS:
HUTT=09013064
CLUTHA=14070121
BULLER=12009639
MANAWATU=07042266
MANUHERIKIKA=14031628
OPIHI=13070002
RANGITAIKI=04029020
RUAMAHANGA=09012311
WAIPAOA=05013426
# WAIRAU=11016544
WAIRAU=11016543
WANGANUI=07030483

cd $HOME/running

# TOPNET_AND_VIS STARTING ==============================================
task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

# TOPNET MODEL RUN =====================================================
task_message NORMAL "topnet started for $REFERENCE_TIME"
task_message NORMAL "(nzlam time ${NZLAM_TIME})"

#task_message CRITICAL "TOPNET DISABLED!"
for BASIN in $RANGITAIKI; do
    task_message NORMAL "processing basin $BASIN"
    task_message NORMAL "$RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN"
    $RUN_TOPNET $NZLAM_TIME $STREAMFLOW_TIME $BASIN
    echo TOPNET RETURNED $?
    echo $PWD
done

task_message NORMAL "topnet finished for $REFERENCE_TIME"

# TOPNET VISUALISATION =================================================
task_message NORMAL "topnet vis started for $REFERENCE_TIME"

VIS_TOPNET_SSF=$HOME/bin/vis_topnet_ssf
VIS_TOPNET=$HOME/bin/vis_topnet
cd $HOME/running

if [[ $NZLAM_AGE == old ]]; then
    task_message NORMAL "ssf only ($NZLAM_AGE nzlam)"
    $VIS_TOPNET_SSF $REFERENCE_TIME 

elif [[ $NZLAM_AGE == old ]]; then
    task_message NORMAL "ssf and rrf ($NZLAM_AGE nzlam)"
    $VIS_TOPNET $REFERENCE_TIME 

else
    task_message CRITICAL "unknown \$NZLAM_AGE"
    exit 1
fi

task_message NORMAL "topnet vis finished for $REFERENCE_TIME"

# TOPNET_AND_VIS FINISHED ==============================================
task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
