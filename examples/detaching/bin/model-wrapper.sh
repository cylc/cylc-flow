#/bin/bash
set -e

# A custom wrapper for the 'model' task from examples:detaching.
# See documentation in the Cylc User Guide.

# Check inputs:
# location of pristine native job scripts:
cylc util checkvars -d NATIVESCRIPTS
# path prefix for model stdout and stderr:
cylc util checkvars PREFIX

# Get a temporary copy of the native job scripts:
TDIR=$TMPDIR/detach$$
mkdir -p $TDIR
cp $NATIVESCRIPTS/* $TDIR

# Insert task-specific execution environment in $TDIR/model.sh:
SRCH='echo "model.sh: executing pseudo-executable"'
perl -pi -e "s@^${SRCH}@${CYLC_SUITE_REG_NAME_ENVIRONMENT}\n${SRCH}@" $TDIR/model.sh

# Task completion message scripting. Use single quotes here - we don't
# want the $? variable to evaluate in this shell!
MSG='
if [[ $? != 0 ]]; then
   cylc task message -p CRITICAL "ERROR: model executable failed"
   exit 1
else
   cylc task succeeded
   exit 0
fi'
# Insert error detection and cylc messaging in $TDIR/model.sh:
SRCH='echo "model.sh: done"'
perl -pi -e "s@^${SRCH}@${MSG}\n${SRCH}@" $TDIR/model.sh

# Point to the temporary copy of model.sh, in run-model.sh:
SRCH='SCRIPT=model.sh'
perl -pi -e "s@^${SRCH}@SCRIPT=$TDIR/model.sh@" $TDIR/run-model.sh

# Execute the (now modified) native process:
$TDIR/run-model.sh ${PREFIX}-${CYLC_TASK_CYCLE_TIME}-$$.out ${PREFIX}-${CYLC_TASK_CYCLE_TIME}-$$.err

echo "model-wrapper.sh: see modified job scripts under ${TDIR}!"
# EOF
