#!/bin/bash

# A custom cylc wrapper for:
#   VAR 26v1.0 AnalsyePF.

# Copy a processed VARUI job, insert cylc messaging and replace some
# suite- and cycle-specific parameters in the job scripts, then run the
# job.

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check compulsory inputs
cylcutil checkvars CYCLE_TIME \
                   VAR_OBDIR_LIST \
                   VAR_CXDIR_LIST \
                   VAR_UMANALINC \
                   VAR_LSDUMP_DIR \
                   GEN_OUTPUT_DIR \
                   GEN_RUN_DIR \
                   GEN_BUILD_DIR

cylcutil checkvars -d VARUI_JOB_DIR
cylcutil checkvars -c TMPDIR

# list of available optional variable replacements
OPTIONAL="
VAR_COVACC
VAR_RHPARMS_DIR
VAR_SATRADCOEFFS_DIR
VAR_RTTOV7COEFFS_DIR
VAR_UMGRID
VAR_PFRECONGRID"

# Set default replacement indicators to false (i.e. do not replace variable)
for OPT in $OPTIONAL; do
    eval REPLACE_${OPT}=false
done

[[ -z VAR_WRAPPER_OPTIONAL_REPLACEMENTS ]] && VAR_WRAPPER_OPTIONAL_REPLACEMENTS=""

# Set indicators for ordered replacements 
for REP in $VAR_WRAPPER_OPTIONAL_REPLACEMENTS; do
    FOUND=false
    for OPT in $OPTIONAL; do
        if [[ $REP == $OPT ]]; then
            FOUND=true
            break
        fi
    done
    if ! $FOUND; then
        cylc task-failed "$REP is not a known OPS wrapper replacement variable"
        exit 1
    else 
        eval REPLACE_${REP}=true
    fi
done

# Report what will be replaced in the job scripts
echo "Optional Replacements:"
for OPT in $OPTIONAL; do
    eval REPLACE=\$REPLACE_$OPT
    if $REPLACE; then
        echo " +     REPLACING ... $OPT"
        # check that the required variable is defined
        cylcutil checkvars $OPT
     else
        echo " + not replacing ... $OPT"
    fi
done
 
# create output directories if necessary
# WARNING: THIS ASSUMES A COMMON FILESYSTEM WITH THE VAR TARGET MACHINE
cylcutil checkvars -p VAR_UMANALINC 
cylcutil checkvars -c GEN_OUTPUT_DIR GEN_RUN_DIR

# check there is only one processed job in the OPSUI job dir
# (if changed the UI job ID without clearing out the old job).
N_JOBS=$( ls $VARUI_JOB_DIR/Var_*_init | wc -l )
if (( N_JOBS == 0 )); then
    cylc task-failed "No processed job found in $VARUI_JOB_DIR"
    exit 1
elif (( N_JOBS > 1 )); then 
    cylc task-failed "More than one processed job found in $VARUI_JOB_DIR"
    exit 1
fi

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

# is this an AnalysePF job?
ANALYSE_PF=false
if ! grep 'program="VarScr_AnalysePF"' $JOB_COMP > /dev/null 2>&1; then
    cylc task-failed 'This is not a VAR AnalysePF job'
    exit 1
fi

# inputs
perl -pi -e "s@(export VAR_OBDIR_LIST=).*@\1${VAR_OBDIR_LIST}@" $JOB_LIST
perl -pi -e "s@(export VAR_CXDIR_LIST=).*@\1${VAR_CXDIR_LIST}@" $JOB_LIST
perl -pi -e "s@(export VAR_LSDUMP_DIR=).*@\1${LSDUMP_DIR}@" $JOB_LIST
# outputs
perl -pi -e "s@(export VAR_UMANALINC=).*@\1${VAR_UMANALINC}@" $JOB_LIST

# gen_path_rel2abs is a shell function defined in Var_<JOBID>_submit_task
perl -pi -e "s@(export GEN_OUTPUT_DIR=.*gen_path_rel2abs ).*@\1${GEN_OUTPUT_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_OUTPUT_TOPDIR=.*gen_path_rel2abs ).*@\1${GEN_OUTPUT_DIR} \\\$HOME \)@" $JOB_FINAL

perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

# control directories
$REPLACE_VAR_COVACC && \
    perl -pi -e "s@(export VAR_COVACC=).*@\1${VAR_COVACC}@" $JOB_LIST
$REPLACE_VAR_RHPARMS_DIR && \
    perl -pi -e "s@(export VAR_RHPARMS_DIR=).*@\1${VAR_RHPARMS_DIR}@" $JOB_LIST
$REPLACE_VAR_SATRADCOEFFS_DIR && \
    perl -pi -e "s@(export VAR_SATRADCOEFFS_DIR=).*@\1${VAR_SATRADCOEFFS_DIR}@" $JOB_LIST
$REPLACE_VAR_RTTOV7COEFFS_DIR && \
    perl -pi -e "s@(export VAR_RTTOV7COEFFS_DIR=).*@\1${VAR_RTTOV7COEFFS_DIR}@" $JOB_LIST
$REPLACE_VAR_UMGRID && \
    perl -pi -e "s@(export VAR_UMGRID=).*@\1${VAR_UMGRID}@" $JOB_LIST
$REPLACE_VAR_PFRECONGRID && \
    perl -pi -e "s@(export VAR_PFRECONGRID=).*@\1${VAR_PFRECONGRID}@" $JOB_LIST

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
