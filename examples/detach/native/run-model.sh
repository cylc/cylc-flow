#!/bin/bash
set -e
echo "run-model.sh ${CYCLE_TIME}: submitting model.sh to 'at now'"
SCRIPT=model.sh  # location of the model job to submit
OUT=$1; ERR=$2   # stdout and stderr log paths
# submit the job and detach
at now <<EOF
$SCRIPT 1> $OUT 2> $ERR
EOF
echo "run-model.sh ${CYCLE_TIME}: done"
