#!/bin/bash

EVENT=$1
SUITE=$2
TASK=$3
MSG=$4

printf "%-20s %-8s %s\n" "$EVENT" $TASK "$MSG" >> $EVNTLOG
 
