#!/bin/bash

SOURCE=$1
filename=$2
FILEPA="'Got $filename'"
test=`ssh $SOURCE "grep $FILEPA /var/log/ecoconnect*"`
echo "Test: $test"
