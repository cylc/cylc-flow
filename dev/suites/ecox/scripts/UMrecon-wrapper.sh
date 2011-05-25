#!/bin/bash

# CYLC CUSTOM TASK WRAPPER for UM 7.4 RECONFIGURATION-ONLY JOBS AT NIWA.

#_______________
# REQUIRED INPUT:
# + $CYCLE_TIME       ..... YYYYMMDDHH
# + $UMUI_JOBDIR      ..... processed umui job files
# + $UMRECON_INPUTDUMP .... input UM model dump to reconfigure
# + $UMRECON_OUTPUTDUMP ... output reconfigured model dump

#_______________
# OPTIONAL INPUT:
# Other parameters this wrapper can replace in the UMUI job files.
# + $UMRECON_LOGDIR   ..... location of the output .leave file

set -e; trap 'cylc task-failed "error trapped"' ERR 

cylc task-started || exit 1

# required inputs
cylcutil check-vars CYCLE_TIME
cylcutil check-vars -d UMUI_JOBDIR
cylcutil check-vars -f UMRECON_INPUTDUMP
cylcutil check-vars -p UMRECON_OUTPUTDUMP

cylcutil check-vars -c TMPDIR

# check optional inputs
REPLACE_UMRECON_LOGDIR=false
cylcutil check-vars UMRECON_LOGDIR && REPLACE_LOGDIR=true
$REPLACE_UMRECON_LOGDIR && cylcutil check-vars -c UMRECON_LOGDIR

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
perl -pi -e "s@( AINITIAL='AINITIAL: ).*@\1${UMRECON_INPUTDUMP}',@" $INITHIS
perl -pi -e "s@( ASTART=  'ASTART  : ).*@\1${UMRECON_OUTPUTDUMP}',@" $INITHIS

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
. $CYLC_DIR/environment.sh

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

# modify UMSUBMIT to use JOBDIR as processed dir
JOBDIR_UP=$( dirname $JOBDIR )
perl -pi -e "s|^processedDir=.*$|processedDir=${JOBDIR}|" $UMSUBMIT

$REPLACE_UMRECON_LOGDIR && \
    perl -pi -e "s|^export MY_OUTPUT=.*$|export MY_OUTPUT=${UMRECON_LOGDIR}|" $SUBMIT

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
