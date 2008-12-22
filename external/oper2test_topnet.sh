#!/bin/bash

set -e  # abort on error

# load functions
echo "WARNING: USING TEMPORARY BAD HARDWIRED FUNCTIONS PATH"
. /test/ecoconnect_test/sequenz/external/functions.sh

trap 'task_message CRITICAL "$TASK_NAME failed"' ERR

# Find the operational tn_\${REFERENCE_TIME}_utc_nzlam_12.nc(.bz2)
# file and copy it to hydrology_\$SYS/input/topnet/ for use by topnet.
# Search order:
#  1. nwp_oper/output/nzlam_12/
#  2. main archive: \$ARCHIVE/YYYYMM/DD/
#  3. staging archive: (stored according to date of harvest)
#  4. (old controller) wait on operational log message

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME

# INTENDED USER:
# * hydrology_(test|dvel)

# test this script on an existing nwp_oper/output tn file by:
#  + changing OPER_LOG to /var/log/ecoconnect-test
#  + disabling the initial nwp_oper file search
#  + kicking the test log with the right message
#    MSG="retrieving met UM file(s) for $REFERENCE_TIME"
#    logger -i -p local1.info -t process_nzlam_output $MSG 


if [[ -z $REFERENCE_TIME ]]; then
	task_message CRITICAL "REFERENCE_TIME not defined"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task_message CRITICAL "TASK_NAME not defined"
	exit 1
fi

task_message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

FILENAME=tn_${REFERENCE_TIME}_utc_nzlam_12.nc

# temporary directory for bunzip2'ing
TMPDIR=/tmp/$USER  
mkdir -p $TMPDIR

# search locations
ARCHIVE=/archive/oper/archive
STAGING=/oper/archive
OUTPUT=/oper/nwp_oper/output/nzlam_12

# target directory
TARGET_DIR=$HOME/input/topnet

# operational log to watch
OPER_LOG=/var/log/ecoconnect

if [[ ! -d $TARGET_DIR ]]; then
    task_message NORMAL "WARNING: creating ${TARGET_DIR}; it should exist already"
    mkdir -p $TARGET_DIR
fi

# determine month and day
YYYYMM=${REFERENCE_TIME%????}
DDHH=${REFERENCE_TIME#??????}
DD=${DDHH%??}
	
# task_message NORMAL "searching for $FILENAME"

SEARCH_MAIN=$ARCHIVE/$YYYYMM/$DD/$FILENAME
SEARCH_NWP=$OUTPUT/$FILENAME

UPTODATE=false

# Search the entire staging archive first, because files are stored there
# according to insertion date, not reference time.  A full search is not
# prohibitive as files are shipped regularly to the main archive. 
FILE_STAGED=false
FOO=$( find $STAGING -name ${FILENAME}'*' )
if [[ -f $FOO ]]; then
    FILE_STAGED=true
    if [[ $FOO = *.bz2 ]];the
        # copy to /tmp for bunzip2'ing in case we don't have write access
        cp ${STAGING/$FILENAME}.bz2 $TMPDIR
        bunzip2 $TMPDIR/${FILENAME}.bz2
        FOO=$TMPDIR/$FILENAME
    else
        FOUND=$FOO
    fi
fi

if $FILE_STAGED; then
    task_message NORMAL "found $FILENAME in staging archive"
    FOUND=$FOO

elif [[ -f $SEARCH_NWP ]]; then
    task_message NORMAL "found $FILENAME in nwp_oper/output/nzlam_12"
    # TO DO: (LONG SHOT) CHECK THAT THE FILE IS COMPLETE?
    # (size check twice, or compare with known file size)
    FOUND=$SEARCH_NWP

elif [[ -f $SEARCH_MAIN ]]; then
    task_message NORMAL "found $FILENAME in main archive"
    FOUND=$SEARCH_MAIN

elif [[ -f ${SEARCH_MAIN}.bz2 ]]; then
    task_message NORMAL "... found  $FILENAME in main archive"
    # copy to /tmp for bunzip2'ing in case we don't have write access
    cp ${SEARCH_MAIN}.bz2 $TMPDIR
    bunzip2 $TMPDIR/${FILENAME}.bz2
    FOUND=$TMPDIR/$FILENAME

else
    task_message WARNING "$FILENAME not found; waiting on $OPER_LOG"
    UPTODATE=true
    # Alert the controller to the fact that we've caught up
    # THE FOLLOWING MESSAGE HAS TO MATCH WHAT THE CONTROLLER EXPECTS
    task_message NORMAL "UPTODATE: waiting for operational tn file for $REFERENCE_TIME"
    while true; do
        if grep "retrieving met UM file(s) for $REFERENCE_TIME" $OPER_LOG; then
            # this message means the tn has been converted to nc and llcleaned
            task_message NORMAL "$OPER_LOG says $FILENAME is ready"
            if [[ -f $SEARCH_NWP ]]; then
                task_message NORMAL "$FILENAME found in $OUTPUT"
                FOUND=$SEARCH_NWP
                break
            else
                task_message CRITICAL "FILE NOT FOUND: $SEARCH_NWP"
                exit 1
            fi
        fi
        sleep 10
    done
fi

if ! $UPTODATE; then
    # Alert the controller to the fact that we're in catch up mode
    # THE FOLLOWING MESSAGE HAS TO MATCH WHAT THE CONTROLLER EXPECTS
    task_message NORMAL "CATCHUP: operational tn file already exists for $REFERENCE_TIME"
fi
 
# copy file to my output directory
task_message NORMAL "copying file to $TARGET_DIR"
cp $FOUND $TARGET_DIR
task_message WARNING "COMPENSATING FOR UM2NETCDF TOTAL_PRECIP ATTRIBUTES BUG"
cd $TARGET_DIR
ncatted -a coordinates,total_precip,o,c,"latitude longitude" $FILENAME
ncatted -a coordinates,sfc_temp,o,c,"latitude longitude" $FILENAME
ncatted -a coordinates,sfc_rh,o,c,"latitude longitude" $FILENAME
task_message NORMAL "file $FILENAME ready"
task_message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
