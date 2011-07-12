#!/bin/bash
set -e
echo "run-model.sh: submitting model.sh to 'at now'"
SCRIPT=model.sh  # location of the model job to submit
OUT=$1; ERR=$2   # stdout and stderr log paths
# submit the job and detach
RES=$TMPDIR/atnow$$.txt
( at now <<EOF
$SCRIPT 1> $OUT 2> $ERR
EOF
) > $RES 2>&1
if grep 'No atd running' $RES; then
    echo 'ERROR: atd is not running!'
    exit 1
fi
# model.sh should now be running at the behest of the 'at' scheduler.
echo "run-model.sh: done"
