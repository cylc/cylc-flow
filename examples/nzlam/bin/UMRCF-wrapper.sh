#!/bin/bash

# A custom cylc wrapper for:
#   UM 7.4 model reconfiguration jobs.

# SCRIPT: UM_DATAW=$DATADIR/$RUNID
# This is where initial PE output goes before being
# combined and moved to $MY_OUTPUT.
# UM_DATAM is probably not needed for RCF jobs.

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check compulsory inputs
# WARNING: $MY_OUTPUT is defined by UM .profile at login
# so be sure to override it in the task environment.
cylcutil checkvars CYCLE_TIME \
                   AINITIAL \
                   ASTART \
                   UM_DATAM \
                   UM_DATAW \
                   MY_OUTPUT

cylcutil checkvars -d UMUI_JOBDIR
cylcutil checkvars -c TMPDIR

# create output directories if necessary
# WARNING: THIS ASSUMES A COMMON FILESYSTEM WITH THE UM TARGET MACHINE
cylcutil checkvars -c MY_OUTPUT UM_DATAM UM_DATAW
cylcutil checkvars -p AINITIAL ASTART MY_OUTPUT

# THERE ARE CURRENTLY NO OPTIONAL REPLACEMENTS. If this changes, handle
# as in the UM forecast job wrapper.

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

# A standalone UM reconfiguration reconfigurs AINITIAL to ASTART
#       INITHIS: AINITIAL='AINITIAL: /path/to/startdump'
perl -pi -e "s@( AINITIAL='AINITIAL: ).*@\1${AINITIAL}',@" $INITHIS
perl -pi -e "s@( ASTART=  'ASTART  : ).*@\1${ASTART}',@" $INITHIS
perl -pi -e "s|^export MY_OUTPUT=.*$|export MY_OUTPUT=${MY_OUTPUT}|" $SUBMIT
perl -pi -e "s|^UM_DATAM=.*$|UM_DATAM=${UM_DATAM}|" $SCRIPT
perl -pi -e "s|^UM_DATAW=.*$|UM_DATAW=${UM_DATAW}|" $SCRIPT

# modify UMSUBMIT to use JOBDIR as processed dir
perl -pi -e "s|^processedDir=.*$|processedDir=${JOBDIR}|" $UMSUBMIT

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
. $CYLC_DIR/environmenet.sh

eof

cat $SCRIPT >> $TMPFILE 
mv $TMPFILE $SCRIPT

# APPEND success test and final cylc task-messages 

cat >> $SCRIPT <<eof
if (( RC != 0 )); then
    cylc task-failed "CYLC UM-WRAPPER: JOB FAILED"
else
    cylc task-message --all-outputs-completed
    cylc task-finished
fi
eof

# remote host
RHOST_LINE=$( grep 'RHOST_NAME=' $SUBMIT )
RHOST=${RHOST_LINE#*=}

USER=$(whoami)

# submit the job
chmod 755 $UMSUBMIT
echo $UMSUBMIT -h $RHOST $JOBID stage_1_submit
$UMSUBMIT -h $RHOST -u $USER $JOBID stage_1_submit
echo SUBMISSION COMPLETED: $?
