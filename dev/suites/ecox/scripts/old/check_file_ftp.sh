#!/bin/bash

# NOT FINISHED - DO NOT USE

# Check if a single file is available on a ftp site.
# Requires .netrc file to be set up to allow automatic ftp server login

# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# Main Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
n=0
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"

#export no_proxy=192.168.0.0/16,niwa.co.nz

# Check the number of arguments
if [ "$#" -ne 7 ]; then
        # FATAL ERROR
        MSG="There needs to be 7 arguments present."
        cylc task-message -p CRITICAL $MSG
        cylc task-failed
        echo "`date -u +%Y%m%d%S%Z` $msgout $MSG"
        exit 1
fi

expectedfiles=1

# Arguments
SOURCE=$1
FILE_DIR=$2
FILE_NAME=$3
SERVICE=$4
TIMEOUT=$5
CYLC_MESSAGE=$6
OUTPUT_DIR=$7

echo "`date -u +%Y%m%d%T%Z`; $msgout Arguments: "
echo "  SOURCE:       ${SOURCE}"
echo "  FILE_DIR:     ${FILE_DIR}"
echo "  FILE_NAME:    ${FILE_NAME}"
echo "  SERVICE:      ${SERVICE}"
echo "  TIMEOUT:      ${TIMEOUT}"
echo "  CYLC_MESSAGE: ${CYLC_MESSAGE}"
echo "  OUTPUT_DIR:   ${OUTPUT_DIR}"

$NAGIOS $SERVICE OK $MSG

# Output directory and ls files
cd $OUTPUT_DIR
LSOLD=ls_${FILE_NAME}_old.txt
LSNEW=ls_${FILE_NAME}_new.txt
touch $LSOLD

# Check until files are present on ftp site
while true; do
# Get a list of files from the ftp server
# lftp should not have any tabs in script (e.g. between EOF)
lftp << EOF
open ${SOURCE} 
cd ${FILE_DIR}
rels > $LSNEW
close
quit	
EOF
    # Note: grep returns exit 1 if it does not find what you searched
    # for. So we trap the exit 1 using the if ! so that cylc does
    # not trap it and exit as failed.
    #
	# grep for the file
    if ! testls=`grep ${FILE_NAME} ${LSNEW}`; then
        echo "`date -u +%Y%m%d%T%Z`; $msgout File not found"
    else
        echo "`date -u +%Y%m%d%T%Z`; $msgout File found, checking again in one minute to see if size changed before sending message."
    fi
    # grep for the file from the previous time they were checked
    if ! testlsold=`grep ${FILE_NAME} ${LSOLD}`; then
        echo "`date -u +%Y%m%d%T%Z`; $msgout File not found in old"
    fi
    # check the number of files
    if ! numberfiles=`grep -c ${FILE_NAME} ${LSNEW}`; then
        echo "`date -u +%Y%m%d%T%Z`; $msgout Number of files not found"
    else
        echo "`date -u +%Y%m%d%T%Z`; $msgout Found $numberfiles files out of $expectedfiles."
    fi
	# Compare the grep results to see if they are the same (includes file sizes and names)
    # This assumes that no change has occured in the past minutes. It
    # does not mean the file is complete (hence there is a risk). However if a file is on the
    # ftp site of the UK MetOffice, it means that it is complete as it
    # has been moved (mv) from its original location.
	if [ "$testls" = "$testlsold" -a "$numberfiles" = "$expectedfiles" ]
	then
		echo "`date -u +%Y%m%d%T%Z`; $msgout Content the same - file $FILE_NAME found on $SOURCE"
        rm -f ${LSNEW} ${LSOLD}
        MSG="`date -u +%Y%m%d%T%Z`; $msgout Finished"
        echo $MSG
        cylc task-message $CYLC_MESSAGE
        # SUCCESS MESSAGE
        cylc task-finished
        exit 0
	else
        
        echo "`date -u +%Y%m%d%T%Z`; $msgout Trying again (n=$n) to check for ${FILE_NAME} on ${SOURCE}, be back in 1 minute"
        n=$((n+1))
        cp ${LSNEW} ${LSOLD}
        if [ $n = $TIMEOUT ]; then
            MSG="$msgout $FILE_NAME on ${SOURCE} has not been found yet in the past $TIMEOUT minutes."
            echo "`date -u +%Y%m%d%T%Z`; $MSG"
            cylc task-message -p CRITICAL $MSG
            $NAGIOS $SERVICE CRITICAL $MSG
        fi
        sleep 60
	fi
done
