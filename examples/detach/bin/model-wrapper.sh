#/bin/bash
set -e

# A custom wrapper for the 'model' task from examples:detach.
# See documentation in the Cylc User Guide, Section 8.4.3.

# Check inputs:
# location of pristine native job scripts:
cylc util checkvars -d NATIVESCRIPTS
# path prefix for model stdout and stderr:
cylc util checkvars OUTPUT_PREFIX

# Get a temporary copy of the native job scripts:
TDIR=$TMPDIR/detach$$
mkdir -p $TDIR
cp $NATIVESCRIPTS/* $TDIR

echo "model-wrapper.sh: modifying model scripts in $TDIR"

# Insert cylc task execution environment in $TDIR/model.sh:
REPL='echo "model.sh: executing pseudo-executable"'
perl -pi -e "s@^${REPL}@${CUSTOM_TASK_WRAPPER_ENVIRONMENT}\n${REPL}@;" $TDIR/model.sh

# Insert error detection and cylc messaging in $TDIR/model.sh:
MSG='
if [[ $? != 0 ]]; then
   cylc task message -p CRITICAL "ERROR: model executable failed"
   exit 1
else
   cylc task succeeded
   exit 0
fi'
REPL='echo "model.sh: done"'
perl -pi -e "s@^${REPL}@${MSG}\n${REPL}@" $TDIR/model.sh

# Point to the temporary copy of model.sh, in run-model.sh:
REPL='SCRIPT=model.sh'
perl -pi -e "s@^${REPL}@SCRIPT=$TDIR/model.sh@" $TDIR/run-model.sh

# Execute the (now modified) native process:
$TDIR/run-model.sh ${OUTPUT_PREFIX}-${CYCLE_TIME}.out ${OUTPUT_PREFIX}-${CYCLE_TIME}.err

# EOF
