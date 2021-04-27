#!/usr/bin/env bash

EVENT="$1"
#WORKFLOW="$2"
TASK="$3"
MSG="$4"

printf "%-20s %-8s %s\n" "${EVENT}" "${TASK}" "${MSG}" >> "${EVNTLOG}"
