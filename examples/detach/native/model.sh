#!/bin/bash
set -e

MODEL="sleep 10; true"      
#MODEL="sleep 10; false"  # uncomment to test model failure

echo "model.sh: executing pseudo-executable"
eval $MODEL
echo "model.sh: done"

