#!/bin/bash

# Hilary Oliver, NIWA, 2010

# A custom cylc wrapper for VAR 26v1.0 ConfigureLS and AnalsyePF jobs.

# This script copies the job directory of a processed VARUI standalone
# job, inserts cylc messaging, replaces suite- and cycle-specific
# parameters, and then runs the job.

# Inputs:
#   $VARUI_JOB_DIR
# And other variables checked immediately below (documentation TBD).

# Note: operational branch UKMO-Wrappers also explicitly replace many
# UM, OPS and VAR control files (stationlists, biase coeffs, etc.).

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check inputs
cylcutil check-vars CYCLE_TIME
cylcutil check-vars -d VARUI_JOB_DIR

cylcutil check-vars -c TMPDIR RUNNING_DIR

# check there is only one processed job in the job dir (in case the user
# changed job ID in the UI and forgot to clear out the old job).
N_JOBS=$( ls $VARUI_JOB_DIR/Var_*_init | wc -l )
if (( N_JOBS == 0 )); then
    cylc task-failed "No processed job found in $VARUI_JOB_DIR"
    exit 1
elif (( N_JOBS > 1 )); then 
    cylc task-failed "More than one processed job found in $VARUI_JOB_DIR"
    exit 1
fi
# VAR control directories ...
cylcutil check-vars -d CYLC_VAR_GRID \
                       CYLC_VAR_RC_PPXREFU_DIR \
                       CYLC_UM_STASHMASTER \
                       CYLC_UM_ANCILMASTER \
                       CYLC_VAR_RHPARMS_DIR \
                       CYLC_VAR_SATRADCOEFFS_DIR \
                       CYLC_VAR_RTTOV7COEFFS_DIR \
                       CYLC_VAR_UMGRID \
                       CYLC_VAR_PFRECONGRID

# build directory
cylcutil check-vars -d CYLC_VAR_BUILD_DIR

# ... and files
cylcutil check-vars -f CYLC_VERT_LEV \
                       CYLC_VAR_COVACC \


# copy processed UI output to a temporary location
JOB_DIR=$TMPDIR/$( basename $VARUI_JOB_DIR ).$$
echo "temporary job dir: $JOB_DIR"
rm -rf $JOB_DIR
mkdir -p $( dirname $JOB_DIR )
cp -r $VARUI_JOB_DIR $JOB_DIR

# VARUI files we need to modify
JOB_INIT=$( ls $JOB_DIR/Var_*_init )
JOBID=${JOB_INIT##*/}
JOBID=${JOBID%_init}
JOBID=${JOBID#*_}
JOB_FINAL=$JOB_DIR/Var_${JOBID}_final
JOB_SUBMIT_TASK=$JOB_DIR/Var_${JOBID}_submit_task
JOB_LIST=$JOB_DIR/VarList_$JOBID
JOB_COMP=$JOB_DIR/VarComp_$JOBID

# is this a ConfigureLS or AnalysePF job?
CONFIGURE_LS=false
ANALYSE_PF=false
grep 'program="VarScr_AnalysePF"' $JOB_COMP > /dev/null 2>&1 && ANALYSE_PF=true
grep 'program="VarScr_ConfigureLS"' $JOB_COMP > /dev/null 2>&1 && CONFIGURE_LS=true
if ! $CONFIGURE_LS && ! $ANALYSE_PF; then
    cylc task-failed 'This is not a ConfigureLS or AnalysePF VAR job'
    exit 1
fi

if $CONFIGURE_LS; then
    # input LS background from UM previous cycle
    cylcutil check-vars TEMPLATE_LSBACK_DIR
    export PPVAR_DIR=$( cylcutil template -s 6 TEMPLATE_LSBACK_DIR )
    cylcutil check-vars -d PPVAR_DIR
else
    cylcutil check-vars TEMPLATE_LOGFILE_DIR \
                        TEMPLATE_VAROB_DIR \
                        TEMPLATE_VARCX_DIR \
                        TEMPLATE_VAR_INCR_FILE
    # input varob and varcx from OPS this cycle
    export VAROB_DIR=$( cylcutil template TEMPLATE_VAROB_DIR )
    export VARCX_DIR=$( cylcutil template TEMPLATE_VARCX_DIR )
    cylcutil check-vars -d VAROB_DIR VARCX_DIR
    # output from AnalysePF
    export VAR_INCREMENTS_FILE=$( cylcutil template TEMPLATE_VAR_INCR_FILE )
    # ensure the output directory exists
    cylcutil check-vars -p VAR_INCREMENTS_FILE
fi

# output from ConfigureLS, input to AnalysePF
cylcutil check-vars TEMPLATE_LSDUMP_DIR
export LSDUMP_DIR=$( cylcutil template TEMPLATE_LSDUMP_DIR )
cylcutil check-vars -c LSDUMP_DIR

# stdout, stderr, stats, etc.
export LOGFILE_DIR=$( cylcutil template TEMPLATE_LOGFILE_DIR )/$TASK_NAME
cylcutil check-vars -c LOGFILE_DIR

# control directories
perl -pi -e "s@(export VAR_GRID=).*@\1${CYLC_VAR_GRID}@" $JOB_LIST
perl -pi -e "s@(export VAR_RC_PPXREFU_DIR=).*@\1${CYLC_VAR_RC_PPXREFU_DIR}@" $JOB_LIST
perl -pi -e "s@(export UM_STASHMASTER=).*@\1${CYLC_UM_STASHMASTER}@" $JOB_LIST
perl -pi -e "s@(export UM_ANCILMASTER=).*@\1${CYLC_UM_ANCILMASTER}@" $JOB_LIST
perl -pi -e "s@(export VERT_LEV=).*@\1${CYLC_VERT_LEV}@" $JOB_LIST
perl -pi -e "s@(export VAR_COVACC=).*@\1${CYLC_VAR_COVACC}@" $JOB_LIST
perl -pi -e "s@(export VAR_RHPARMS_DIR=).*@\1${CYLC_VAR_RHPARMS_DIR}@" $JOB_LIST
perl -pi -e "s@(export VAR_SATRADCOEFFS_DIR=).*@\1${CYLC_VAR_SATRADCOEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export VAR_RTTOV7COEFFS_DIR=).*@\1${CYLC_VAR_RTTOV7COEFFS_DIR}@" $JOB_LIST
perl -pi -e "s@(export VAR_UMGRID=).*@\1${CYLC_VAR_UMGRID}@" $JOB_LIST
perl -pi -e "s@(export VAR_PFRECONGRID=).*@\1${CYLC_VAR_PFRECONGRID}@" $JOB_LIST

if $CONFIGURE_LS; then
    # inputs
    perl -pi -e "s@(export VAR_UMBACK_DIR=).*@\1${PPVAR_DIR}@" $JOB_LIST
else
    # inputs
    perl -pi -e "s@(export VAR_OBDIR_LIST=).*@\1${VAROB_DIR}@" $JOB_LIST
    perl -pi -e "s@(export VAR_CXDIR_LIST=).*@\1${VARCX_DIR}@" $JOB_LIST
    # outputs
    perl -pi -e "s@(export VAR_UMANALINC=).*@\1${VAR_INCREMENTS_FILE}@" $JOB_LIST
fi
# outputs
perl -pi -e "s@(export VAR_LSDUMP_DIR=).*@\1${LSDUMP_DIR}@" $JOB_LIST

# gen_path_rel2abs is a shell function defined in Var_<JOBID>_submit_task
perl -pi -e "s@(export GEN_OUTPUT_DIR=.*gen_path_rel2abs ).*@\1${LOGFILE_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_OUTPUT_TOPDIR=.*gen_path_rel2abs ).*@\1${LOGFILE_DIR} \\\$HOME \)@" $JOB_FINAL

perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${RUNNING_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_VAR_BUILD_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_VAR_BUILD_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${CYLC_VAR_BUILD_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

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
. $CYLC_DIR/environment.sh

if (( RC != 0 )); then
    cylc task-failed 'CYLC VAR WRAPPER: Job Failed'
else
    echo CYLC VAR WRAPPER: Job Finished
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
