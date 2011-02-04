#!/bin/bash

# Generate an NZLAM ALABC file for current cycle (T) from 21 3-hourly
# T-6 frames:
#  YYYYMMDD_frame_qgHH_niwa_(0,3,6,..,60).gz

# Generate an NZLAM ALABC file for current cycle (T)
# from 21 3-hourly T-6 global frames files:
#    YYYYMMDD_frame_qgHH_niwa_(0,3,6,..,60).gz

# Frames are uncompressed to a working directory.

# Main input environment variable:
#  + $MAKEBC_NAMELIST - makebc control namelist

# Commandline options:
#  + --keep         - do not delete uncompressed frames files
#  + --force        - regenerate ALABC file if it already exists

# Access to makebc executable is required, via the UM environment:
#. ~um_fcm/user-config/um.profile
# (currently sourced in the taskdef %EXTRA_SCRIPTING section).

# THIS IS A WRAPPED CYLC TASK SCRIPT

set -e; trap 'cylc task-message -p CRITICAL "error trapped"' ERR

# command line args
KEEP=false
FORCE=false
[[ $# > 2 ]] && {
    cylc task-message -p CRITICAL "too many arguments"
    exit 1
}
[[ $@ = *--keep*  ]] && KEEP=true
[[ $@ = *--force* ]] && FORCE=true

# check input variables
cylcutil check-vars -c TMPDIR
cylcutil check-vars TEMPLATE_ALABC_FILE TEMPLATE_FRAMES_FILE
cylcutil check-vars -f MAKEBC_NAMELIST

FRAMES_NUMBER=21

WORKING_DIR=$TMPDIR
ALABC_FILE=$( cylcutil template TEMPLATE_ALABC_FILE )
# make sure LBC output directory exists
mkdir -p $( dirname $ALABC_FILE )

FRAMES_PREFIX=$( cylcutil template -s 6 $TEMPLATE_FRAMES_FILE )

if [[ -f $ALABC_FILE ]] && ! $FORCE; then
    cylc task-message "finished (ALABC file already exists)"
    exit 0
fi

# generate a list of all frames filenames, sans ".gz"
N=0
FILE_LIST=""
while (( N < FRAMES_NUMBER )); do
    FILE_LIST="$FILE_LIST ${FRAMES_PREFIX}_$(( N * 3 ))"
    N=$(( N + 1 ))
done

# uncompress gzipped frames files into $WORKING_DIR
cd $WORKING_DIR
for FILE in $FILE_LIST; do
    F_IN=$FRAMES_DIR/${FILE}.gz
    if [[ -f $FILE ]]; then
        echo "$FILE already exists"
    elif [[ -f $F_IN ]]; then
        echo "uncompressing $F_IN"
        gunzip -c $F_IN > $FILE
    else
        # report failed
        cylc task-message -p CRITICAL "file not found $F_IN"
        exit 1
    fi
done

# run makebc to generate output ALABC file
makebc -n $MAKEBC_NAMELIST -i $FILE_LIST -o $ALABC_FILE || {
    cylc task-message -p CRITICAL "makebc failed"
    exit 1
}

# delete ucompressed frames files
if $KEEP; then
    echo "Option '--keep' => NOT deleting uncompressed frames"
else
    echo "deleting uncompressed frames files in $WORKING_DIR"
    rm $FILE_LIST
fi

# FINISHED
