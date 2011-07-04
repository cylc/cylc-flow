#!/bin/bash
set -e

MODEL="sleep 10; true"      # test success
#MODEL="sleep 10; false"    # test failure

echo "model.sh: executing pseudo-executable"
eval $MODEL
echo "model.sh: done"

