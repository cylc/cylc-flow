#!/bin/bash

# Hilary Oliver, NIWA, 2010

# A custom cylc wrapper for UM 7.4 model run jobs.
# IF RECONFIGURATION IS REQUIRED RUN IT AS A SEPARATE TASK.

# This script copies the job directory of a processed standalone UMUI
# job, inserts cylc messaging, replaces suite- and cycle-specific
# parameters, and then runs the job.

#_______________
# REQUIRED INPUT:
# + $CYCLE_TIME   ..... YYYYMMDDHH
# + $UMUI_JOBDIR  ..... processed umui job files
# + $UM_STARTDUMP ..... UM model start dump

#_______________
# OPTIONAL INPUT:
# Other parameters this wrapper can replace in the UMUI job files.
# + $UM_LOGDIR   ..... location of the output .leave file
# + $UM_PP7CXFILE  ... OPS STASH Macro output file
# + $UM_PPVARFILE  ... VAR STASH Macro output file
# + $UM_DATAMDIR
# + $UM_DATAWDIR
# + $UM_EXECUTABLE
# + $UM_ALABCFILE
# + $UM_VARINCFILE

# MINOR CHANGE REQUIRED WHEN WE GO TO 4D-VAR: the UM 4D VAR stash macro
# writes multiple reinitialized files to $DATAM.

set -e; trap 'cylc task-failed "error trapped"' ERR 

cylc task-started || exit 1

# required inputs
cylcutil check-vars CYCLE_TIME
cylcutil check-vars -d UMUI_JOBDIR
cylcutil check-vars -f UM_STARTDUMP

cylcutil check-vars -c TMPDIR

# optional inputs
REPLACE_UM_DATAMDIR=false
cylcutil check-vars UM_DATAMDIR && REPLACE_UM_DATAMDIR=true
$REPLACE_UM_DATAMDIR && cylcutil check-vars -c UM_DATAMDIR

REPLACE_UM_DATAWDIR=false
cylcutil check-vars UM_DATAWDIR && REPLACE_UM_DATAWDIR=true
$REPLACE_UM_DATAWDIR && cylcutil check-vars -c UM_DATAWDIR

REPLACE_UM_PP7CXFILE=false
cylcutil check-vars UM_PP7CXFILE && REPLACE_UM_PP7CXFILE=true
$REPLACE_UM_PP7CXFILE && cylcutil check-vars -p UM_PP7CXFILE

REPLACE_UM_PPVARFILE=false
cylcutil check-vars UM_PPVARFILE && REPLACE_UM_PPVARFILE=true
$REPLACE_UM_PPVARFILE && cylcutil check-vars -p UM_PPVARFILE

REPLACE_UM_EXECUTABLE=false
cylcutil check-vars UM_EXECUTABLE && REPLACE_UM_EXECUTABLE=true
$REPLACE_UM_EXECUTABLE && cylcutil check-vars -f UM_EXECUTABLE

REPLACE_UM_ALABCFILE=false
cylcutil check-vars UM_ALABCFILE && REPLACE_UM_ALABCFILE=true
$REPLACE_UM_ALABCFILE && cylcutil check-vars -f UM_ALABCFILE

REPLACE_UM_VARINCFILE=false
cylcutil check-vars UM_VARINCFILE && REPLACE_UM_VARINCFILE=true
$REPLACE_UM_VARINCFILE && cylcutil check-vars -f UM_VARINCFILE

REPLACE_UM_LOGDIR=false
cylcutil check-vars UM_LOGDIR && REPLACE_UM_LOGDIR=true
$REPLACE_UM_LOGDIR && cylcutil check-vars -c UM_LOGDIR

# copy processed UI output to a temporary location
JOBDIR=$TMPDIR/$( basename $UMUI_JOBDIR ).$$
echo "temporary job dir: $JOBDIR"
rm -rf $JOBDIR
mkdir -p $( dirname $JOBDIR )
cp -r $UMUI_JOBDIR $JOBDIR

# get the UM RUNID
JOBID_LINE=$( grep 'RUNID=' $JOBDIR/SUBMIT )
JOBID=${JOBID_LINE#*=}

# jobdir files we need
SUBMIT=$JOBDIR/SUBMIT
UMSUBMIT=$JOBDIR/UMSUBMIT
SCRIPT=$JOBDIR/SCRIPT
INITHIS=$JOBDIR/INITHIS

# In the following perl expressions, if using '@' as the regex separator, do
# not use '$' immediately before '@', because $@ is interpreted by the shell.

# start dump is ASTART
#  INITHIS: ASTART=  'ASTART  : /path/to/startdump'
perl -pi -e "s@( ASTART=  'ASTART  : ).*@\1${UM_STARTDUMP}',@" $INITHIS

$REPLACE_UM_PPVARFILE && \
    perl -pi -e "s@( PPVAR='PPVAR   : ).*@\1${UM_PPVARFILE}',@" $INITHIS

$REPLACE_UM_PP7CXFILE && \
    perl -pi -e "s@( PP7='PP7     : ).*@\1${UM_PP7CXFILE}',@" $INITHIS

$REPLACE_UM_ALABCFILE && \
    perl -pi -e "s@( ALABCIN1= 'ALABCIN1: ).*@\1${UM_ALABCFILE}',@" $INITHIS

$REPLACE_UM_VARINCFILE && \
    perl -pi -e "s@( IAU_inc= 'IAU_inc: ).*@\1${UM_VARINCFILE}',@" $INITHIS

$REPLACE_UM_DATAMDIR && \
    perl -pi -e "s|^UM_DATAM=.*$|UM_DATAM=${UM_DATAMDIR}|" $SCRIPT

$REPLACE_UM_DATAWDIR && \
    perl -pi -e "s|^UM_DATAW=.*$|UM_DATAW=${UM_DATAWDIR}|" $SCRIPT

$REPLACE_UM_EXECUTABLE && \
    perl -pi -e "s|^export LOADMODULE=.*$|export LOADMODULE=${UM_EXECUTABLE}|" $SCRIPT

$REPLACE_UM_LOGDIR && \
    perl -pi -e "s|^export MY_OUTPUT=.*$|export MY_OUTPUT=${UM_LOGDIR}|" $SUBMIT

# modify SCRIPT for cylc.
TMPFILE=$TMPDIR/um-wrapper.$$

# PREPEND cylc environment
cat >> $TMPFILE <<eof
# MINIMAL CYLC ENVIRONMENT FOR ACCESS TO 'cylc task-message' ETC.
export CYLC_SUITE_NAME=$CYLC_SUITE_NAME
export CYLC_SUITE_OWNER=$CYLC_SUITE_OWNER
export CYLC_SUITE_HOST=$CYLC_SUITE_HOST
export CYLC_SUITE_PORT=$CYLC_SUITE_PORT
export CYLC_MODE=$CYLC_MODE
export CYLC_USE_LOCKSERVER=$CYLC_USE_LOCKSERVER
export CYCLE_TIME=$CYCLE_TIME
export TASK_NAME=$TASK_NAME
export TASK_ID=$TASK_ID
export CYLC_DIR=$CYLC_DIR
. $CYLC_DIR/cylc-env.sh

eof

cat $SCRIPT >> $TMPFILE 
mv $TMPFILE $SCRIPT

# APPEND success test and final cylc task-messages 
cat >> $SCRIPT <<EOF
if (( RC != 0 )); then
    cylc task-failed "CYLC UM-WRAPPER: JOB FAILED"
else
    cylc task-message --all-outputs-completed
    cylc task-finished
fi
EOF

# modify UMSUBMIT to use JOBDIR as processed dir
JOBDIR_UP=$( dirname $JOBDIR )
perl -pi -e "s|^processedDir=.*$|processedDir=${JOBDIR}|" $UMSUBMIT

# remote host
RHOST_LINE=$( grep 'RHOST_NAME=' $SUBMIT )
RHOST=${RHOST_LINE#*=}

USER=$(whoami)

# submit the job
chmod 755 $UMSUBMIT
echo $UMSUBMIT -h $RHOST $JOBID stage_1_submit
$UMSUBMIT -h $RHOST -u $USER $JOBID stage_1_submit
echo SUBMISSION COMPLETED: $?

# EOF
