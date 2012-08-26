#!/bin/bash

echo
echo "HELLO FROM TASK EVENT HANDLER"

EVENT=$1
SUITE=$2
TASK=$3
MSG=$4

ARGS="EVENT SUITE TASK MSG"
for ITEM in $ARGS; do
    echo "  $ITEM $( eval echo \$$ITEM )"
done

echo "BYE FROM TASK EVENT HANDLER"
echo
