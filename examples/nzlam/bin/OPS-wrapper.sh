#!/bin/bash

# A custom cylc wrapper for:
#   OPS 26v1.0 Extract And Process from Obstore.

# Copy a processed OPSUI job, insert cylc messaging and replace some
# suite- and cycle-specific parameters in the job scripts, then run.

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check compulsory inputs
cylcutil checkvars CYCLE_TIME \
                   OPS_OBSTORE_DIR \
                   OPS_UMBACK_LIST \
                   OPS_BACKERR \
                   OPS_LISTING_DIR \
                   OPS_VAROB_DIR \
                   OPS_CX_DIR_LIST \
                   GEN_OUTPUT_DIR \
                   GEN_RUN_DIR \
                   GEN_BUILD_DIR

cylcutil checkvars -d OPSUI_JOB_DIR
cylcutil checkvars -c TMPDIR

# list of available optional variable replacements
OPTIONAL="
OPS_SATRADSTATS_DIR
OPS_AIRSSTATS_DIR
OPS_SCATSTATS_DIR
OPS_STATIONLIST_DIR
OPS_SONDECOEFFS_DIR
OPS_RTTOV7COEFFS_DIR
OPS_SATRADCOEFFS_DIR
OPS_SATRADBIASES_DIR
OPS_SATWINDNL_DIR
OPS_SCATWINDCOEFFS_DIR
OPS_GPSROCOEFFS_DIR"

# Set default replacement indicators to false (i.e. do not replace variable)
for OPT in $OPTIONAL; do
    eval REPLACE_${OPT}=false
done

[[ -z OPS_WRAPPER_OPTIONAL_REPLACEMENTS ]] && OPS_WRAPPER_OPTIONAL_REPLACEMENTS=""

# Set indicators for ordered replacements 
for REP in $OPS_WRAPPER_OPTIONAL_REPLACEMENTS; do
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
cylcutil checkvars -c GEN_OUTPUT_DIR \
                      GEN_RUN_DIR \
                      OPS_LISTING_DIR \
                      OPS_VAROB_DIR \
                      OPS_CX_DIR_LIST
# now the optional dirs
$REPLACE_OPS_SATRADSTATS_DIR && cylcutil checkvars -c OPS_SATRADSTATS_DIR
$REPLACE_OPS_AIRSSTATS_DIR   && cylcutil checkvars -c OPS_AIRSSTATS_DIR
$REPLACE_OPS_SCATSTATS_DIR   && cylcutil checkvars -c OPS_SCATSTATS_DIR

# check there is only one processed job in the OPSUI job dir
# (if changed the UI job ID without clearing out the old job).
N_JOBS=$( ls $OPSUI_JOB_DIR/Ops_*_init | wc -l )
if (( N_JOBS == 0 )); then
    cylc task-failed "No processed OPS job found in $OPSUI_JOB_DIR"
    exit 1
elif (( N_JOBS > 1 )); then 
    cylc task-failed "More than one processed OPS job found in $OPSUI_JOB_DIR"
    exit 1
fi

# copy processed UI output to a temporary location
JOB_DIR=$TMPDIR/$( basename $OPSUI_JOB_DIR ).$$
rm -rf $JOB_DIR
mkdir -p $( dirname $JOB_DIR )
cp -r $OPSUI_JOB_DIR $JOB_DIR

# Identify the OPS job files that we need to modify
JOB_INIT=$( ls $JOB_DIR/Ops_*_init )
JOBID=${JOB_INIT##*/}
JOBID=${JOBID%_init}
JOBID=${JOBID#*_}
JOB_FINAL=$JOB_DIR/Ops_${JOBID}_final
JOB_SUBMIT_TASK=$JOB_DIR/Ops_${JOBID}_submit_task
JOB_LIST=$JOB_DIR/OpsList_$JOBID

# OPS housekeeping time
OPS_YEAR=$(  cylcutil cycletime --year )
OPS_MONTH=$( cylcutil cycletime --month)
OPS_DAY=$(   cylcutil cycletime --day  )
OPS_HOUR=$(  cylcutil cycletime --hour )

# can't follow backrefs (\1) with digits (OPS_YEAR etc.) in Perl 5.8.8 at least.
perl -pi -e "s@(export OPS_YEAR=).*@\1REPLACE_ME${OPS_YEAR}@" $JOB_LIST
perl -pi -e "s@(export OPS_MONTH=).*@\1REPLACE_ME${OPS_MONTH}@" $JOB_LIST
perl -pi -e "s@(export OPS_DAY=).*@\1REPLACE_ME${OPS_DAY}@" $JOB_LIST
perl -pi -e "s@(export OPS_HOUR=).*@\1REPLACE_ME${OPS_HOUR}@" $JOB_LIST 
perl -pi -e "s/REPLACE_ME//g" $JOB_LIST

# replace run-dependent inputs in the JOB_LIST file
perl -pi -e "s@(export OPS_OBSTORE_DIR=).*@\1${OPS_OBSTORE_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_UMBACK_LIST=).*@\1\"${OPS_UMBACK_LIST}\"@" $JOB_LIST
perl -pi -e "s@(export OPS_BACKERR=).*@\1${OPS_BACKERR}@" $JOB_LIST

# listing and stats outputs
perl -pi -e "s@(export OPS_LISTING_DIR=).*@\1${OPS_LISTING_DIR}@" $JOB_LIST

# job output directories (varobs and cx files)
perl -pi -e "s@(export OPS_VAROB_DIR=).*@\1${OPS_VAROB_DIR}@" $JOB_LIST
perl -pi -e "s@(export OPS_CX_DIR_LIST=).*@\1\"${OPS_CX_DIR_LIST}\"@" $JOB_LIST

# gen_path_rel2abs is a shell function defined in Ops_<JOBID>_submit_task
perl -pi -e "s@(export GEN_OUTPUT_DIR=.*gen_path_rel2abs ).*@\1${GEN_OUTPUT_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_OUTPUT_TOPDIR=.*gen_path_rel2abs ).*@\1${GEN_OUTPUT_DIR} \\\$HOME \)@" $JOB_FINAL

perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_RUN_DIR=.*gen_path_rel2abs ).*@\1${GEN_RUN_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_INIT
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_FINAL
perl -pi -e "s@(export GEN_BUILD_DIR=.*gen_path_rel2abs ).*@\1${GEN_BUILD_DIR} \\\$HOME \)@" $JOB_SUBMIT_TASK

# satellite stats outputs
$REPLACE_OPS_SATRADSTATS_DIR    && \
    perl -pi -e "s@(export OPS_SATRADSTATS_DIR=).*@\1${OPS_SATRADSTATS_DIR}@" $JOB_LIST
$REPLACE_OPS_AIRSSTATS_DIR      && \
    perl -pi -e "s@(export OPS_AIRSSTATS_DIR=).*@\1${OPS_AIRSSTATS_DIR}@" $JOB_LIST
$REPLACE_OPS_SCATSTATS_DIR      && \
    perl -pi -e "s@(export OPS_SCATSTATS_DIR=).*@\1${OPS_SCATSTATS_DIR}@" $JOB_LIST
# control directories
$REPLACE_OPS_STATIONLIST_DIR    && \
    perl -pi -e "s@(export OPS_STATIONLIST_DIR=).*@\1${OPS_STATIONLIST_DIR}@" $JOB_LIST
$REPLACE_OPS_SONDECOEFFS_DIR    && \
    perl -pi -e "s@(export OPS_SONDECOEFFS_DIR=).*@\1${OPS_SONDECOEFFS_DIR}@" $JOB_LIST
$REPLACE_OPS_RTTOV7COEFFS_DIR   && \
    perl -pi -e "s@(export OPS_RTTOV7COEFFS_DIR=).*@\1${OPS_RTTOV7COEFFS_DIR}@" $JOB_LIST
$REPLACE_OPS_SATRADCOEFFS_DIR   && \
    perl -pi -e "s@(export OPS_SATRADCOEFFS_DIR=).*@\1${OPS_SATRADCOEFFS_DIR}@" $JOB_LIST
$REPLACE_OPS_SATRADBIASES_DIR   && \
    perl -pi -e "s@(export OPS_SATRADBIASES_DIR=).*@\1${OPS_SATRADBIASES_DIR}@" $JOB_LIST
$REPLACE_OPS_SATWINDNL_DIR      && \
    perl -pi -e "s@(export OPS_SATWINDNL_DIR=).*@\1${OPS_SATWINDNL_DIR}@" $JOB_LIST
$REPLACE_OPS_SCATWINDCOEFFS_DIR && \
    perl -pi -e "s@(export OPS_SCATWINDCOEFFS_DIR=).*@\1${OPS_SCATWINDCOEFFS_DIR}@" $JOB_LIST
$REPLACE_OPS_GPSROCOEFFS_DIR    && \
    perl -pi -e "s@(export OPS_GPSROCOEFFS_DIR=).*@\1${OPS_GPSROCOEFFS_DIR}@" $JOB_LIST

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
