#!/bin/bash

set -e  # abort on error

# source sequenz environment
. $SEQUENZ_ENV

trap 'task-message CRITICAL "$TASK_NAME failed"' ERR

# Find the operational tn_\${REFERENCE_TIME}_utc_nzlam_12.nc(.bz2)
# file and copy it to hydrology_\$SYS/input/topnet/ for use by topnet.
# Search order (see below for why I search the staging archive first):
#  2. nwp_oper/output/nzlam_12/
#  3. main archive: \$ARCHIVE/YYYYMM/DD/
#  1. staging archive: (stored according to date of harvest)
#  4. (old controller) wait on operational log message

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME
#   3. $SEQUENZ_ENV

# INTENDED USER:
# * hydrology_(test|dvel)

# test this script on an existing nwp_oper/output tn file by:
#  + changing OPER_LOG to /var/log/ecoconnect-test
#  + disabling the initial nwp_oper file search
#  + kicking the test log with the right message
#    MSG="retrieving met UM file(s) for $REFERENCE_TIME"
#    logger -i -p local1.info -t process_nzlam_output $MSG 


if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
    task-message CRITICAL "$TASK_NAME failed"
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
    task-message CRITICAL "$TASK_NAME failed"
	exit 1
fi

task-message NORMAL "$TASK_NAME started for $REFERENCE_TIME"

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
    task-message NORMAL "WARNING: creating ${TARGET_DIR}; it should exist already"
    mkdir -p $TARGET_DIR
fi

# determine month and day
YYYYMM=${REFERENCE_TIME%????}
DDHH=${REFERENCE_TIME#??????}
DD=${DDHH%??}
	
# task-message NORMAL "searching for $FILENAME"

SEARCH_MAIN=$ARCHIVE/$YYYYMM/$DD/$FILENAME
SEARCH_NWP=$OUTPUT/$FILENAME

CAUGHTUP=false

# Search the entire staging archive first, because files are stored there
# according to insertion date, not reference time.  A full search is not
# prohibitive as files are shipped regularly to the main archive. 
FOO=$( find $STAGING -name ${FILENAME} )
FOOBZ=$( find $STAGING -name ${FILENAME}.bz2 )

if [[ -f $FOO ]]; then
    echo NORMAL "found $FILENAME in staging archive"
    FOUND=$FOO

elif [[ -f $FOOBZ ]]; then
    echo NORMAL "found ${FILENAME}.bz2 in staging archive"
    # copy to /tmp for bunzip2'ing in case we don't have write access
    cp $FOOBZ $TMPDIR
    bunzip2 $TMPDIR/${FILENAME}.bz2
    FOUND=$TMPDIR/$FILENAME

elif [[ -f $SEARCH_NWP ]]; then
    task-message NORMAL "found $FILENAME in nwp_oper/output/nzlam_12"
    # TO DO: (LONG SHOT) CHECK THAT THE FILE IS COMPLETE?
    # (size check twice, or compare with known file size)
    FOUND=$SEARCH_NWP

elif [[ -f $SEARCH_MAIN ]]; then
    task-message NORMAL "found $FILENAME in main archive"
    FOUND=$SEARCH_MAIN

elif [[ -f ${SEARCH_MAIN}.bz2 ]]; then
    task-message NORMAL "... found  $FILENAME in main archive"
    # copy to /tmp for bunzip2'ing in case we don't have write access
    cp ${SEARCH_MAIN}.bz2 $TMPDIR
    bunzip2 $TMPDIR/${FILENAME}.bz2
    FOUND=$TMPDIR/$FILENAME

else
    task-message WARNING "$FILENAME not found; waiting on $OPER_LOG"
    CAUGHTUP=true
    # Alert the controller to the fact that we've caught up
    # THE FOLLOWING MESSAGE HAS TO MATCH WHAT THE CONTROLLER EXPECTS
    task-message NORMAL "CAUGHTUP: waiting for operational tn file for $REFERENCE_TIME"
    while true; do
        if grep "failed to convert tn\*_${REFERENCE_TIME}_\*.um to netcdf" $OPER_LOG > /dev/null; then
            # this means the operational file conversion failed
            task-message CRITICAL "$OPER_LOG indicates $FILENAME netcdf conversion failed"
            task-message CRITICAL "$TASK_NAME failed"
            exit 1
        fi
        if grep "retrieving met UM file(s) for $REFERENCE_TIME" $OPER_LOG > /dev/null; then
            # this means the tn file has been converted to netcdf and llcleaned
            task-message NORMAL "$OPER_LOG indicates $FILENAME is ready"
            if [[ -f $SEARCH_NWP ]]; then
                task-message NORMAL "$FILENAME found in $OUTPUT"
                FOUND=$SEARCH_NWP
                break
            else
                task-message CRITICAL "FILE NOT FOUND: $SEARCH_NWP"
                task-message CRITICAL "$TASK_NAME failed"
                exit 1
            fi
        fi
        sleep 10
    done
fi

if ! $CAUGHTUP; then
    # Alert the controller to the fact that we're in catch up mode
    # THE FOLLOWING MESSAGE HAS TO MATCH WHAT THE CONTROLLER EXPECTS
    task-message NORMAL "CATCHINGUP: operational tn file already exists for $REFERENCE_TIME"
fi
 
# copy file to my output directory
task-message NORMAL "copying file to $TARGET_DIR"
cp $FOUND $TARGET_DIR
# The following is no longer necessary as llclean has been fixed, and TopNet
# made backward compatible (for missing attributes) in older tn_.nc files.
#task-message WARNING "COMPENSATING FOR UM2NETCDF TOTAL_PRECIP ATTRIBUTES BUG"
#cd $TARGET_DIR
#ncatted -a coordinates,total_precip,o,c,"latitude longitude" $FILENAME
#ncatted -a coordinates,sfc_temp,o,c,"latitude longitude" $FILENAME
#ncatted -a coordinates,sfc_rh,o,c,"latitude longitude" $FILENAME
task-message NORMAL "file $FILENAME ready"
task-message NORMAL "$TASK_NAME finished for $REFERENCE_TIME"
