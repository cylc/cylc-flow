#!/bin/bash
# run-model.sh
echo "run-model.sh: submitting model.sh to 'at now'"
SCRIPT=model.sh
OUT=$1
ERR=$2
# submit job and detach
at now <<EOF
$SCRIPT 1> $OUT 2> $ERR
EOF
echo "run-model.sh: bye"
