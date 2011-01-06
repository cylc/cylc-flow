#!/bin/bash

NAME=$1
CTIME=$2
REASON=$3

echo "!TASK FAILURE ALERT!"
echo " > Task $NAME failed for $CTIME"
echo " > reason: $REASON"
