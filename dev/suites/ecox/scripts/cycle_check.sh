#!/bin/bash
#
# Check if a cycle is completely finished and show statistics each tasks.
#
# This is a cylc wrapped script
#
# Author: Bernard Miville
# Date: 14 September 2010
#
# Environment variables:
#   1. MAIN_LOG_FILE    - Name of the main cylc log file
#   2. MAIN_LOG_DIR     - Location of the main cylc log file
#   3. TASK_LIST_FILE   - File containing all the tasks for all cycle
#   4. TASK_LIST_DIR    - Directory where the task list file is located 
#   5. OUTPUT_FILE      - CSV file output name (Prefix only)
#   6. OUTPUT_DIR       - Output directory for the csv file
#
# Trap errors so that we need not check the success of basic operations.
set -e

# Main Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
SERVICE="cycle_check"
n=0

# Print environment variables list
echo "`date -u +%Y%m%d%T%Z`; $msgout Arguments: "
echo "  1- MAIN_LOG_FILE:    ${MAIN_LOG_FILE}"
echo "  2- MAIN_LOG_DIR:     ${MAIN_LOG_DIR}"
echo "  3- TASK_LIST_FILE:    ${TASK_LIST_FILE}"
echo "  4- TASK_LIST_DIR:    ${TASK_LIST_DIR}"
echo "  4- OUTPUT_FILE:      ${OUTPUT_FILE}"
echo "  5- OUTPUT_DIR:       ${OUTPUT_DIR}"

# Check the environment variables
# Directories
cylcutil check-vars -d MAIN_LOG_DIR TASK_LIST_DIR OUTPUT_DIR
# Variables
cylcutil check-vars MAIN_LOG_FILE TASK_LIST_FILE OUTPUT_FILE

# Send NAGIOS OK message
$NAGIOS $SERVICE OK "$msgout Started"

# Output file
OUT_CSV_FILE=${OUTPUT_FILE}
rm -f ${OUTPUT_DIR}/${OUT_CSV_FILE}
echo ${CYCLE_TIME} > ${OUTPUT_DIR}/${OUT_CSV_FILE}

# Hour
HH=${CYCLE_TIME:8:2}

# Get task for the current Cycle Hour
grep $HH ${TASK_LIST_DIR}/${TASK_LIST_FILE} > ${TASK_LIST_DIR}/latest_task.csv

# backup current IFS (Internal File Separator)
IFS_backup="${IFS}"

# change IFS to a comma
IFS=","

while read taskcheck ctime
do

    # grep for started task
    if ! started=$(grep -h "${taskcheck}%${CYCLE_TIME} started" ${MAIN_LOG_DIR}/${MAIN_LOG_FILE}); then
       echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Task $taskcheck not found in ${MAIN_LOG_DIR}/${MAIN_LOG_FILE}"
      started="Not found"
    fi
    # grep for finished task
    if ! finished=$(grep -h "$taskcheck%${CYCLE_TIME} finished" ${MAIN_LOG_DIR}/${MAIN_LOG_FILE}); then
       echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Task $taskcheck not found in ${MAIN_LOG_DIR}/${MAIN_LOG_FILE}"
       finished="Not found"
    fi
    started=${started:0:19}
    finished=${finished:0:19}
    timediff="Not available"
    if [ "$started" != "Not found" ] && [ "$finished" != "Not found" ]; then
        started_s=`date +%s -d"$started"`
        finished_s=`date +%s -d"$finished"`
        timediff=$((($finished_s-$started_s)/60))
	timediff=`echo "scale=1; (${finished_s}-${started_s})/60"|bc`
    fi
    echo "$taskcheck, ${CYCLE_TIME}, $started, $finished, $timediff" >> ${OUTPUT_DIR}/${OUT_CSV_FILE}
    
done < ${TASK_LIST_DIR}/latest_task.csv

# restore IFS
IFS="${IFS_backup}"

# Copy output file to latest file
cp ${OUTPUT_DIR}/${OUT_CSV_FILE} ${OUTPUT_DIR}/task_stats_latest.csv

# Send Finished and NAGIOS OK message
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
$NAGIOS $SERVICE OK "$msgout Finished"
