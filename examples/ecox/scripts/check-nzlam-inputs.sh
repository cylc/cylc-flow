#!/bin/bash

# Retrieve NZLAM suite input files for the current cycle, uncompressing
# or unpacking them if necessary.

# This script currently just looks in the expected file locations and
# could be split into separate scripts for each file type. However, it
# will be extended to look further afield if the files are not found.

# THIS SCRIPT, AND THE TEMPLATES IT USES, HAS BEEN ADAPTED FROM THE
# STANDALONE NZLAM SUITE, AND SHOULD BE CLEANED UP SOMEWHAT.
# E.G. DON'T COPY IF THE FILE IS ALREADY IN THE INPUT DIRECTORY.

USAGE="Usage: check-nzlam-inputs.sh --obstore|bgerr|frames|globaldump"

if [[ $# != 1 ]]; then
    echo $USAGE
    exit 1
fi

TYPE=$1
CWD=$PWD

SYS=${HOME##*_}
ECOX=/$SYS/ecoconnect/ecoconnect_$SYS/output

if [[ $TYPE = --obstore ]]; then
    # OBSTORE DIRECTORY

    # uncompress and unpack if necessary
    cylcutil check-vars TEMPLATE_OBSTORE_DIR \
                        TEMPLATE_OBSTORE_DIR_TGZ

    export OBSTORE_DIR_TGZ=$(cylcutil template TEMPLATE_OBSTORE_DIR_TGZ )
    ECOX_OBSTORE_DIR_TGZ=$ECOX/$( basename $OBSTORE_DIR_TGZ )
    if [[ ! -f $ECOX_OBSTORE_DIR_TGZ ]]; then
        echo "File not found: $ECOX_OBSTORE_DIR_TGZ"
        exit 1
    fi

    cp $ECOX_OBSTORE_DIR_TGZ $HOME/input

    export OBSTORE_DIR=$(cylcutil template TEMPLATE_OBSTORE_DIR )
    if ! cylcutil check-vars -d OBSTORE_DIR; then
        cylcutil check-vars -f OBSTORE_DIR_TGZ || exit 1
        cd $( dirname $OBSTORE_DIR )
        echo "Unpacking $OBSTORE_DIR_TGZ"
        tar xzf $OBSTORE_DIR_TGZ
        cd $CWD
    fi

elif [[ $TYPE = --bgerr ]]; then
    # BGERR FILE
    # uncompress if necessary
    cylcutil check-vars TEMPLATE_BGERR_FILE

    export BGERR_FILE=$( cylcutil template TEMPLATE_BGERR_FILE ) 
    export BGERR_FILE_GZ=${BGERR_FILE}.gz 
    ECOX_BGERR_FILE_GZ=$ECOX/$( basename ${BGERR_FILE}.gz )
    if [[ ! -f $ECOX_BGERR_FILE_GZ ]]; then
        echo "File not found: $ECOX_BGERR_FILE_GZ"
        exit 1
    fi

    cp $ECOX_BGERR_FILE_GZ $HOME/input

    if ! cylcutil check-vars -f BGERR_FILE; then
        cylcutil check-vars -f BGERR_FILE_GZ || exit 1
        cd $( dirname $BGERR_FILE )
        echo "Uncompressing $BGERR_FILE_GZ"
        gunzip $BGERR_FILE_GZ
        cd $CWD
    fi

elif [[ $TYPE = --frames ]]; then
    # FRAMES FILES
    # do not uncompress; the make_alabc task handles this
    FRAMES_NUMBER=21  # 3-hourly frames files to T+60
    cylcutil check-vars TEMPLATE_FRAMES_FILE
    FRAMES_PREFIX=$( cylcutil template -s 6 $TEMPLATE_FRAMES_FILE )
    # generate a list of all frames filenames, sans ".gz"
    N=0
    FILE_LIST=""
    while (( N < FRAMES_NUMBER )); do
        FILE_LIST="$FILE_LIST ${FRAMES_PREFIX}_$(( N * 3 ))"
        N=$(( N + 1 ))
    done

    COUNT=0
    TOTAL=0
    for FILE in $FILE_LIST; do
        ECOX_FILE=$ECOX/$( basename $FILE )
        TOTAL=$(( TOTAL + 1 ))
        if [[ ! -f ${ECOX_FILE}.gz ]]; then
            COUNT=$(( COUNT + 1 ))
        else
            cp ${ECOX_FILE}.gz $HOME/input
        fi
    done

    if (( COUNT != 0 )); then
        echo "$COUNT frames files not found out of $TOTAL"
        exit 1
    fi

elif [[ $TYPE = --globaldump ]]; then
    # uncompress if necessary
    export STARTDUMP=$( cylcutil template -s 6 $TEMPLATE_REDUCED_GLOBAL_DUMP )
    export STARTDUMP_GZ=${STARTDUMP}.gz

    ECOX_STARTDUMP_GZ=$ECOX/$( basename $STARTDUMP_GZ )
    if [[ ! -f $ECOX_STARTDUMP_GZ ]]; then
        echo "File not found: $ECOX_STARTDUMP_GZ"
        exit 1
    fi

    cp $ECOX_STARTDUMP_GZ $HOME/input

    if ! cylcutil check-vars -f STARTDUMP; then
        cylcutil check-vars -f STARTDUMP_GZ || exit 1
        echo "Uncompressing start dump: $STARTDUMP_GZ"
        gunzip $STARTDUMP_GZ
    fi

else
    # unknown file type requested
    echo $USAGE
    exit 1
fi
