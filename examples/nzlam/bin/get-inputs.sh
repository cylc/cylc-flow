#!/bin/bash

# Hilary Oliver, NIWA, 2010

# Retrieve input files, uncompressing and/or unpacking if necessary.
# For the general master suite, just look in the suite input directory.

USAGE="Usage: get-inputs.sh --obstore|bgerr|frames|globaldump"

if [[ $# != 1 ]]; then
    echo $USAGE
    exit 1
fi

TYPE=$1
CWD=$PWD

if [[ $TYPE = --obstore ]]; then
    # OBSTORE DIRECTORY
    # uncompress and unpack if necessary
    cylcutil checkvars OBSTORE_DIR
    if [[ ! -d $OBSTORE_DIR ]]; then
        if [[ -f $OBSTORE_DIR_TGZ ]]; then 
            cd $( dirname $OBSTORE_DIR )
            echo "Unpacking $OBSTORE_DIR_TGZ"
            tar xzf $OBSTORE_DIR_TGZ
            cd $CWD
        else
            echo "Obstores not found: $OBSTORE_DIR or $OBSTORE_DIR_TGZ" >&2
            exit 1
        fi
    fi

elif [[ $TYPE = --bgerr ]]; then
    # BGERR FILE
    # uncompress if necessary
    cylcutil checkvars BGERR_FILE
    if [[ ! -f $BGERR_FILE ]]; then
        BGERR_FILE_GZ=${BGERR_FILE}.gz 
        if [[ -f BGERR_FILE_GZ ]]; then
            cd $( dirname $BGERR_FILE )
            echo "Uncompressing $BGERR_FILE_GZ"
            gunzip $BGERR_FILE_GZ
            cd $CWD
        else
            echo "File not found: ${BGERR_FILE}(.gz)" >&2
            exit 1
        fi
    fi

elif [[ $TYPE = --frames ]]; then
    # FRAMES FILES
    # do not uncompress; the make_alabc task handles this
    FRAMES_NUMBER=21  # 3-hourly frames files to T+60
    cylcutil checkvars FRAMES_FILE_PREFIX
    # generate a list of all frames filenames, sans ".gz"
    N=0
    FILE_LIST=""
    while (( N < FRAMES_NUMBER )); do
        FILE_LIST="$FILE_LIST ${FRAMES_FILE_PREFIX}_$(( N * 3 ))"
        N=$(( N + 1 ))
    done

    COUNT=0
    TOTAL=0
    for FILE in $FILE_LIST; do
        TOTAL=$(( TOTAL + 1 ))
        if [[ ! -f $FILE ]] && [[ ! -f ${FILE}.gz ]]; then
            COUNT=$(( COUNT + 1 ))
        fi
    done

    if (( COUNT != 0 )); then
        echo "$COUNT frames files not found out of $TOTAL"
        exit 1
    fi

elif [[ $TYPE = --globaldump ]]; then
    cylcutil checkvars GLOBALDUMP
    # uncompress if necessary
    if [[ ! -f $GLOBALDUMP ]]; then
        GLOBALDUMP_GZ=${GLOBALDUMP}.gz
        if [[ -f $GLOBALDUMP_GZ ]]; then
            echo "Uncompressing start dump: $GLOBALDUMP_GZ"
            gunzip $GLOBALDUMP_GZ
        else:
            echo "File not found: ${GLOBALDUMP}(.gz)" >&2 
            exit 1
        fi
    fi

else
    # unknown file type requested
    echo $USAGE
    exit 1
fi
