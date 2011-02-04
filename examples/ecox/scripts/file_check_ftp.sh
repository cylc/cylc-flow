#!/bin/bash
# Check if a single file is available on a ftp site.
# Requires .netrc file to be set up to allow automatic ftp server login
#
# This is a cylc wrapped script
#
# Author: Bernard Miville
# Date: 26 August 2010
#
# Environment variables:
#   1. SRCE         - Source ftp server address
#   2. SRCE_LOC     - Source ftp directory ("~/" for home, can not be
#                     empty)
#   3. DEST_LOC     - Directory where files are stored while running 
#                     the script
#   4. FILENAME     - Source file name
#   5. SRCE_USER    - Username for ftp site (uses .netrc file for
#                     password)
#   6. SERVICE      - name of NAGIOS service
#   8. TIMEOUT      - Time in minutes before file check stops
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
n=0
expectedfiles=1

# Print environment variables list
echo "`date -u +%Y%m%d%T%Z`; $msgout Arguments: "
echo "  1- SRCE:         ${SRCE}"
echo "  2- SRCE_LOC:     ${SRCE_LOC}"
echo "  3- DEST_LOC:     ${DEST_LOC}"
echo "  4- FILENAME:     ${FILENAME}"
echo "  5- SRCE_USER:    ${SRCE_USER}"
echo "  6- SERVICE:      ${SERVICE}"
echo "  7- TIMEOUT:      ${TIMEOUT}"

# Check the environment variables
# Directories
cylcutil check-vars -d DEST_LOC
# Variables
cylcutil check-vars SRCE \
                    SRCE_LOC \
                    FILENAME \
                    SRCE_USER \
                    SERVICE \
                    TIMEOUT

# Send NAGIOS OK message
$NAGIOS $SERVICE OK "$msgout Started"

# ~/ as root directory does not work with lfpt
if [ $SRCE_LOC = '/' -o $SRCE_LOC = '~/' ]; then
    SRCE_LOC=""
fi

# Output directory and ls files
cd $DEST_LOC
lsold=""

# Check until files are present on ftp site
while true; do
# Get a list of files from the ftp server
    echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Getting a file listing from $SRCE"
    if ! lsnew=$(lftp -c open -e "rels" ftp://${SRCE_USER}@${SRCE}/${SRCE_LOC}); then
        MSG="$msgout Could not connect to $SRCE"
        echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
        cylc task-message -p CRITICAL $MSG
        $NAGIOS $SERVICE CRITICAL $MSG
        exit 1
    fi
    # Note: grep returns exit 1 if it does not find what you searched
    # for. So we trap the exit 1 using the if ! so that cylc does
    # not trap it and exit as failed.
    #
	# grep for the file
    if ! testlsnew=$(echo "$lsnew" | grep "$FILENAME"); then
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout File $FILENAME not found on $SRCE"
    else
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout File $FILENAME found on $SRCE, checking again in one minute to see if size changed before sending message."
    fi
    # grep for the file from the previous time they were checked
    if ! testlsold=$(echo "$lsold" | grep "$FILENAME"); then
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout File $FILENAME not found in old ls"
    fi
    # check the number of files
    if ! numberfiles=$(echo "$lsnew" | grep -c ${FILENAME}); then
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Number of file(s) not found"
    else
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Found $numberfiles file(s) out of $expectedfiles."
    fi
	# Compare the grep results to see if they are the same (includes file sizes and names)
    # This assumes that no change has occured in the past minutes. It
    # does not mean the file is complete (hence there is a risk). However if a file is on the
    # ftp site of the UK MetOffice, it means that it is complete as it
    # has been moved (mv) from its original location.
	if [ "$testlsnew" = "$testlsold" -a "$numberfiles" = "$expectedfiles" ]
	then
		echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Content the same - file $FILENAME found on $SRCE"
        lsold=""
        MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Finished"
        echo $MSG
        # Send NAGIOS OK message
        $NAGIOS $SERVICE OK "$msgout Finished"
        exit 0
	else
        
        echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Trying (n=$n) to check for ${FILENAME} on ${SRCE}, be back in 1 minute"
        n=$((n+1))

        lsold=$lsnew
        if [ $n = $TIMEOUT ]; then
            MSG="$msgout $FILENAME on ${SRCE} has not been found yet in the past $TIMEOUT minutes."
            echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
            cylc task-message -p WARNING $MSG
            # Send a NAGIOS CRITICAL message once
            $NAGIOS $SERVICE CRITICAL $MSG
        fi
        sleep 60 
	fi
done
