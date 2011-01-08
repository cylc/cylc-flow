#!/bin/bash

set -e

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

usage="USAGE: clean-workspace.sh [PATH]"

if [[ $# != 0 ]] && [[ $# != 1 ]]; then
    echo $usage >&2
    exit 1
fi

if [[ $# == 1 ]]; then
    WORKSPACE=$1
else
    echo "No workspace specified for cleaning"
    exit 0
fi

echo "Cleanup $WORKSPACE ..."

rm -rf $WORKSPACE
mkdir -p $WORKSPACE

echo "Done"
