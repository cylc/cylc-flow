#!/bin/bash

# A custom cylc wrapper for:
#   UM 7.4 model run jobs.

# Copy a processed UMUI job, insert cylc messaging and replace some
# suite- and cycle-specific parameters in the job scripts, then run the
# job.

# IF RECONFIGURATION IS REQUIRED RUN IT AS A SEPARATE TASK.

# MINOR CHANGE REQUIRED FOR 4D-VAR?: The UM 4D VAR stash macro writes
# multiple reinitialized files to $UM_DATAM.

set -e; trap 'cylc task-failed "error trapped"' ERR 
cylc task-started || exit 1

# check compulsory inputs
# WARNING: $MY_OUTPUT is defined by UM .profile at login
# so be sure to override it in the task environment.
cylcutil checkvars CYCLE_TIME \
                   ASTART \
                   PP7 \
                   PPVAR \
                   ALABCIN1 \
                   UM_DATAM \
                   UM_DATAW \
                   MY_OUTPUT

cylcutil checkvars -d UMUI_JOBDIR
cylcutil checkvars -c TMPDIR

# create output directories if necessary
# WARNING: THIS ASSUMES A COMMON FILESYSTEM WITH THE UM TARGET MACHINE
cylcutil checkvars -c MY_OUTPUT UM_DATAM UM_DATAW
cylcutil checkvars -p ASTART PP7 PPVAR

# list of available optional variable replacements
OPTIONAL="LOADMODULE IAU_inc"

# Set default replacement indicators to false (i.e. do not replace variable)
for OPT in $OPTIONAL; do
    eval REPLACE_${OPT}=false
done

[[ -z UM_WRAPPER_OPTIONAL_REPLACEMENTS ]] && UM_WRAPPER_OPTIONAL_REPLACEMENTS=""

# Set indicators for ordered replacements 
for REP in $UM_WRAPPER_OPTIONAL_REPLACEMENTS; do
    FOUND=false
    for OPT in $OPTIONAL; do
        if [[ $REP == $OPT ]]; then
            FOUND=true
            break
        fi
    done
    if ! $FOUND; then
        cylc task-failed "$REP is not a known UM wrapper replacement variable"
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
 
#
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
perl -pi -e "s@( ASTART=  'ASTART  : ).*@\1${ASTART}',@" $INITHIS
perl -pi -e "s@( PPVAR='PPVAR   : ).*@\1${PPVAR}',@" $INITHIS
perl -pi -e "s@( PP7='PP7     : ).*@\1${PP7}',@" $INITHIS
perl -pi -e "s@( ALABCIN1= 'ALABCIN1: ).*@\1${ALABCIN1}',@" $INITHIS
perl -pi -e "s|^UM_DATAM=.*$|UM_DATAM=${UM_DATAM}|" $SCRIPT
perl -pi -e "s|^UM_DATAW=.*$|UM_DATAW=${UM_DATAW}|" $SCRIPT
perl -pi -e "s|^export MY_OUTPUT=.*$|export MY_OUTPUT=${MY_OUTPUT}|" $SUBMIT

$REPLACE_LOADMODULE && \
    perl -pi -e "s|^export LOADMODULE=.*$|export LOADMODULE=${LOADMODULE}|" $SCRIPT
$REPLACE_IAU_inc && \
    perl -pi -e "s@( IAU_inc= 'IAU_inc: ).*@\1${IAU_inc}',@" $INITHIS

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

# remote host
RHOST_LINE=$( grep 'RHOST_NAME=' $SUBMIT )
RHOST=${RHOST_LINE#*=}

USER=$(whoami)

# submit the job
chmod 755 $UMSUBMIT
echo $UMSUBMIT -h $RHOST $JOBID stage_1_submit
$UMSUBMIT -h $RHOST -u $USER $JOBID stage_1_submit
echo SUBMISSION COMPLETED: $?
