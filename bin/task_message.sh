#!/bin/bash

# trivial wrapper for 

# USAGE: task_message <PRIORITY> <"MESSAGE">
# priorities are CRITICAL, WARNING, NORMAL

MESSAGER=sequenz_notify.py  
#MESSAGER=echo   # debugging
    
PRIORITY=$1; shift
$MESSAGER $PRIORITY $TASK_NAME $REFERENCE_TIME "$@"
