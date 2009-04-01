#!/bin/bash

# display currently running external dummy tasks
    
HEADING1="Current Running External Dummy Tasks"
HEADING2=$(ps -fu $USER | grep UID | grep -v grep)

OIFS=$IFS
while true; do
    IFS=$OIFS
    FOO=$(ps -fu $USER | grep dummy | grep -v grep )
    clear
    IFS=$'\n'
    echo $HEADING1
    echo -e "\033[34m $HEADING2 \033[0m"
    for line in $FOO; do echo $line; done
    sleep 2
done

