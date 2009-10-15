#!/bin/bash

# THIS IS A CYCLON TASK SCRIPT

set -e  # ABORT ON ERROR

# source cyclon environment
. $CYCLON_ENV

# ABORT IN CASE OF ANY ERROR, AND ALERT CYCLON
# (this means we do not need to explicitly check for success of simple
# operations like directory creation, etc.
trap 'task-message -p CRITICAL failed' ERR  

task-message started  # COMPULSORY START MESSAGE

# Purpose: [describe what this task does]

# Task-specific input (EXAMPLE): 
# 1. $FOO

if [[ -z $FOO ]]; then
    task-message -p CRITICAL "FOO undefined"
    task-message -p CRITICAL failed  # COMPULSORY MESSAGE ON FAILURE
    exit 1 
fi

# ... SCRIPT BODY ...

task-message finished  # COMPULSORY FINISHED MESSAGE

# NOTE: all task scripts are supplied $CYCLON_ENV, $TASK_NAME, and
# $REFERENCE_TIME by cyclon, and do not need to check that these 
# inputs have been defined; task-message checks for that.
