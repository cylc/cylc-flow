#!/bin/bash

# Hilary Oliver, NIWA, 2010

# A custom cylc wrapper for OPS 26v1.0 Extract & Process jobs (obstore).

# This script copies the job directory of a processed standalone OPSUI
# job, inserts cylc messaging, replaces suite- and cycle-specific
# parameters, and then runs the job.

# Inputs:
#   $OPSUI_JOB_DIR
# And other variables checked immediately below (documentation TBD).

# Note: operational branch UKMO-Wrappers also explicitly replace many
# UM, OPS and VAR control files (stationlists, biase coeffs, etc.).

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check inputs
cylcutil check-vars CYCLE_TIME
cylcutil check-vars -d OPSUI_JOB_DIR

cylcutil check-vars -c TMPDIR RUNNING_DIR

# check there is only one processed job in the job dir (in case the user
# changed job ID in the UI and forgot to clear out the old job).
N_JOBS=$( ls $OPSUI_JOB_DIR/Ops_*_init | wc -l )
if (( N_JOBS == 0 )); then
    cylc task-failed "No processed OPS job found in $OPSUI_JOB_DIR"
    exit 1

elif (( N_JOBS > 1 )); then 
    cylc task-failed "More than one processed OPS job found in $OPSUI_JOB_DIR"
    exit 1
fi
# OPS control file directories
cylcutil check-vars -d CYLC_OPS_STATIONLIST_DIR \
                       CYLC_OPS_SONDECOEFFS_DIR \
                       CYLC_OPS_RTTOV7COEFFS_DIR \
                       CYLC_OPS_SATRADCOEFFS_DIR \
                       CYLC_OPS_SATRADBIASES_DIR \
                       CYLC_OPS_SATWINDNL_DIR \
                       CYLC_OPS_SCATWINDCOEFFS_DIR \
                       CYLC_OPS_GPSROCOEFFS_DIR

# build directory
cylcutil check-vars -d CYLC_OPS_BUILD_DIR

cylcutil check-vars TEMPLATE_LOGFILE_DIR \
                    TEMPLATE_LISTING_DIR \
                    TEMPLATE_STATS_DIR \
                    TEMPLATE_OBSTORE_DIR \
                    TEMPLATE_OBSTORE_DIR_TGZ \
                    TEMPLATE_BGERR_FILE \
                    TEMPLATE_PP7CX_FILE \
                    TEMPLATE_VAROB_DIR \
                    TEMPLATE_VARCX_DIR


# copy processed UI output to a temporary location
JOB_DIR=$TMPDIR/$( basename $OPSUI_JOB_DIR ).$$
rm -rf $JOB_DIR
mkdir -p $( dirname $JOB_DIR )
cp -r $OPSUI_JOB_DIR $JOB_DIR

# OPSUI files we need to modify
JOB_INIT=$( ls $JOB_DIR/Ops_*_init )
JOBID=${JOB_INIT##*/}
JOBID=${JOBID%_init}
JOBID=${JOBID#*_}
JOB_FINAL=$JOB_DIR/Ops_${JOBID}_final
JOB_SUBMIT_TASK=$JOB_DIR/Ops_${JOBID}_submit_task
JOB_LIST=$JOB_DIR/OpsList_$JOBID

# input obstore dir and bgerr file
export OBSTORE_DIR=$(cylcutil template TEMPLATE_OBSTORE_DIR )
cylcutil check-vars -d OBSTORE_DIR
export BGERR_FILE=$( cylcutil template TEMPLATE_BGERR_FILE ) 
cylcutil check-vars -f BGERR_FILE

# CX background input from UM previous cycle
export PP7CX_FILE=$( cylcutil template -s 6 TEMPLATE_PP7CX_FILE )
cylcutil check-vars -f PP7CX_FILE

# output stdout, stderr, stats, etc.
export LOGFILE_DIR=$( cylcutil template TEMPLATE_LOGFILE_DIR )/$TASK_NAME
cylcutil check-vars -c LOGFILE_DIR

# output dir for listing files
export LISTING_DIR=$( cylcutil template TEMPLATE_LISTING_DIR )
cylcutil check-vars -c LISTING_DIR

# output dir for stats files
export STATS_DIR=$( cylcutil template TEMPLATE_STATS_DIR )/$TASK_NAME
cylcutil check-vars -c STATS_DIR

# output varobs and varcx files
export VAROB_DIR=$( cylcutil template TEMPLATE_VAROB_DIR )
export VARCX_DIR=$( cylcutil template TEMPLATE_VARCX_DIR )
cylcutil check-vars -c VAROB_DIR VARCX_DIR

# OPS housekeeping time
OPS_YEAR=$(  cylcutil cycle-time --year )
OPS_MONTH=$( cylcutil cycle-time --month)
OPS_DAY=$(   cylcutil cycle-time --day  )
OPS_HOUR=$(  cylcutil cycle-time --hour )

# replace run-dependent inputs in the JOB_LIST file
perl -pi -e "s@(export OPS_OBSTORE_DIR=).*@\1${OBSTORE_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_UMBACK_LIST=).*@\1\"${PP7CX_FILE}\"@" $JOB_LIST
perl -pi -e "s@(export OPS_BACKERR=).*@\1${BGERR_FILE}@" $JOB_LIST

# listing and stats outputs
perl -pi -e "s@(export OPS_LISTING_DIR=).*@\1${LISTING_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SATRADSTATS_DIR=).*@\1${STATS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_AIRSSTATS_DIR=).*@\1${STATS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SCATSTATS_DIR=).*@\1${STATS_DIR}@" $JOB_LIST

# control directories
perl -pi -e "s@(export OPS_STATIONLIST_DIR=).*@\1${CYLC_OPS_STATIONLIST_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SONDECOEFFS_DIR=).*@\1${CYLC_OPS_SONDECOEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_RTTOV7COEFFS_DIR=).*@\1${CYLC_OPS_RTTOV7COEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SATRADCOEFFS_DIR=).*@\1${CYLC_OPS_SATRADCOEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SATRADBIASES_DIR=).*@\1${CYLC_OPS_SATRADBIASES_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SATWINDNL_DIR=).*@\1${CYLC_OPS_SATWINDNL_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_SCATWINDCOEFFS_DIR=).*@\1${CYLC_OPS_SCATWINDCOEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_GPSROCOEFFS_DIR=).*@\1${CYLC_OPS_GPSROCOEFFS_DIR}@" $JOB_LIST

# and the same for outputs
perl -pi -e "s@(export OPS_VAROB_DIR=).*@\1${VAROB_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_CX_DIR_LIST=).*@\1\"${VARCX_DIR}\"@" $JOB_LIST

# gen_path_rel2abs is a shell function defined in Ops_<JOBID>_submit_task
perl -pi -e "s@(export GEN_OUTPUT_DIR=.*gen_path_rel2abs ).*@\1${LOGFILE_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_OUTPUT_TOPDIR=.*gen_path_rel2abs ).*@\1${LOGFILE_DIR} \\\$HOME \)@" $JOB_FINAL

perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_OPS_BUILD_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_OPS_BUILD_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_OPS_BUILD_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

# can't follow backrefs (\1) with digits (OPS_YEAR etc.) in Perl 5.8.8 at least.
perl -pi -e "s@(export OPS_YEAR=).*@\1REPLACE_ME${OPS_YEAR}@" $JOB_LIST
perl -pi -e "s@(export OPS_MONTH=).*@\1REPLACE_ME${OPS_MONTH}@" $JOB_LIST
perl -pi -e "s@(export OPS_DAY=).*@\1REPLACE_ME${OPS_DAY}@" $JOB_LIST
perl -pi -e "s@(export OPS_HOUR=).*@\1REPLACE_ME${OPS_HOUR}@" $JOB_LIST 
perl -pi -e "s/REPLACE_ME//g" $JOB_LIST

# insert final cylc calls in $JOB_FINAL
perl -pi -e "s@(job completed: rc=.*)@\1
# MINIMAL CYLC ENVIRONMENT FOR ACCESS TO cylc task-message
export CYLC_SUITE_NAME=\"$CYLC_SUITE_NAME\"
export CYLC_SUITE_OWNER=\"$CYLC_SUITE_OWNER\"
export CYLC_SUITE_HOST=\"$CYLC_SUITE_HOST\"
export CYLC_SUITE_PORT=\"$CYLC_SUITE_PORT\"
export CYLC_MODE=\"$CYLC_MODE\"
export CYLC_USE_LOCKSERVER=\"$CYLC_USE_LOCKSERVER\"
export CYCLE_TIME=\"$CYCLE_TIME\"
export TASK_NAME=\"$TASK_NAME\"
export TASK_ID=\"$TASK_ID\"
export CYLC_DIR=\"$CYLC_DIR\"
. $CYLC_DIR/cylc-env.sh

if (( RC != 0 )); then
    cylc task-failed 'CYLC OPS WRAPPER: Job Failed'
else
    echo CYLC OPS WRAPPER: Job Finished
    cylc task-message --all-outputs-completed
    cylc task-finished
fi
@" $JOB_FINAL

# 1/ make JOB_INIT executable
chmod 755 $JOB_INIT
# 2/ run JOB_INIT
echo "RUNNING $JOB_INIT"
$JOB_INIT
echo "$JOB_INIT FINISHED"

# EOF
