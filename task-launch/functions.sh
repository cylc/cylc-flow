#!/bin/bash

function task_message 
{
    # USAGE: task_message <PRIORITY> <"MESSAGE">
    # priorities are CRITICAL, WARNING, NORMAL

    # TO DO: WHERE TO KEEP EXTERNAL SCRIPTS AND HOW TO REFER TO THEM
    MESSAGER=/test/ecoconnect_test/sequenz/send_message.py  
    #MESSAGER=echo   # uncomment for debugging
    
    PRIORITY=$1; shift
    $MESSAGER $PRIORITY $TASK_NAME $REFERENCE_TIME "$@"
}
