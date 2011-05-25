#!/bin/bash
# Generic file ftp download
#
# Trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed' ERR

# START MESSAGE
cylc task-started

# Purpose: file ftp transfer.

# Task-specific arguments:
#   1. $SRCE         - Source ftp server address
#   2. $SRCE_LOC     - path at the source
#   3. $DEST_LOC     - path at the destination (Assuming the destination is on the same server as the request)
#   4. $FILENAME     - name of file to transfer
#   5. $SRCE_USER    - username at the source (password assumed to be in .netrc file)   
#   6. $KEEP         - 0 delete file from ftp site
#                      1 leave file on ftp site
#   7. $FAST         - 0 download single file single thread
#                      1 download single file 4 threads
#                      2 Download multiple files single thread
#   8. $FILEOUT      - Destination file name. Not used if downloading
#                      multiple files.
#                      downloads multiple files and do not rename them
#   9. $CYLC_MESSAGE - Ouput message
#   10. $TIMEOUT     - Number of minutes to try finding the file
#   11. $CHECKSUM    - 0 do not do a check sum 
#                      1 do a check sum and compare with downloaded check sum file
#   12. $CHECKFILE   - Name of downloaded check sum file (only required
#                      if $CHECKSUM=1)

# This script is a single-call wrapper for 'lftp' that takes
# its arguments from the arguments list in the taskdef for cylc.

# passwordless lftp must be configured for all transfers. 
# (using the .netrc file in the user root directory)

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
SERVICE="file_transfer_ftp"
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d%T%Z`; $msgout Started"
echo "$MSG"
n=0

# Load arguments
SRCE=$1
SRCE_LOC=$2
DEST_LOC=$3
FILENAME=$4
SRCE_USER=$5
KEEP=$6
FAST=$7
FILEOUT=$8
CYLC_MESSAGE=$9
TIMEOUT=${10}
CHECKSUM=${11}
CHECKFILE=${12}

# Grep does not always like the wildcard *, it uses . instead in
# combination with *
FILEGREP=`echo $FILENAME | sed -e "s/\*/.\*/g"`

# Print arguments list
echo "`date -u +%Y%m%d%T%Z`; $msgout Arguments:"
echo "   SRCE:         ${SRCE}"
echo "   SRCE_LOC:     ${SRCE_LOC}"
echo "   DEST_LOC:     ${DEST_LOC}"
echo "   FILENAME:     ${FILENAME}"
echo "   SRCE_USER:    ${SRCE_USER}"
echo "   KEEP:         ${KEEP}"
echo "   FAST:         ${FAST}"
echo "   FILEOUT:      ${FILEOUT}"
echo "   CYLC_MESSAGE: ${CYLC_MESSAGE}"
echo "   TIMEOUT:      ${TIMEOUT}"
echo "   CHECKSUM:     ${CHECKSUM}"
echo "   CHECKFILE:    ${CHECKFILE}"

# Check for required arguments
if [[ -z $SRCE ]]; then
    MSG="SRCE not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z ${SRCE_LOC} ]]; then
    MSG="SRCE_LOC not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z ${DEST_LOC} ]]; then
    MSG="DEST_LOC not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z ${SRCE_USER} ]]; then
    MSG="SRCE_USER not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z $FILENAME ]]; then
    MSG="FILENAME not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z $KEEP ]]; then
    MSG="KEEP not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi
if [[ -z $FAST ]]; then
    MSG="FAST not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi

if [ $FAST -gt 2 ]; then
    MSG="FAST not witihn allowed range (0,1,2)"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi

if [[ -z $CYLC_MESSAGE ]]; then
    MSG="CYLC_MESSAGE not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi

if [[ -z $CHECKSUM ]]; then
    MSG="CHECKSUM not defined"
    echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
    cylc task-message -p CRITICAL $MSG
    cylc task-failed
    exit 1
fi

if [[ -z $CHECKFILE ]]; then
    if [ $CHECKSUM = 1 ]; then
        MSG="CHECKFILE not defined"
        echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
        cylc task-message -p CRITICAL $MSG
        cylc task-failed
        exit 1
    fi
 fi
# ~/ as root directory does not work with lfpt 
if [ $SRCE_LOC = '/' -o $SRCE_LOC = '~/' ]; then
     SRCE_LOC=""
fi

# Check if file is there and download it

while true; do
    # First check if you can connect to ftp site
	if ! testfile=$(curl --silent --list-only --netrc --connect-timeout 60 --disable-epsv ftp://$SRCE_USER@$SRCE$SRCE_LOC); then
		MSG="Could not connect to source: $SRCE"
        echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
        cylc task-message -p CRITICAL $MSG
        cylc task-failed
        exit 1
	fi
    # Download file if there
    echo "`date -u +%Y%m%d%T%Z`; $msgout Trying to download $FILENAME from $SRCE"
    # First make sure the file is in the listing. If not there it will
    # try again until the TIMEOUT.
    # A grep will exit with 0 if it finds the $FILENAME and 1 if it does
    # not find it. The if is used to avoid an exit failure trap by
    # cylc.
	if echo "$testfile" | grep "$FILEGREP" >/dev/null 2>&1
        then
        echo "`date -u +%Y%m%d%T%Z`; $msgout Found file $FILENAME at $SRCE, will send message to cylc"
		# Start downloading
        MSG="initiating file transfer for $FILENAME from $SRCE to ${DEST_LOC}"
		cylc task-message $MSG
		MSG="Downloading $FILENAME from $SRCE ${SRCE_LOC} to ${DEST_LOC}"
		echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
		cd $DEST_LOC

		if [ $KEEP = 1 -a $FAST = 0 ]; then
		#       Download file normally and leave it on ftp site
		        echo "`date -u +%Y%m%d%T%Z`; $msgout lftp -d -c \"get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
		        lftp -d -c "get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"
		elif [ $KEEP = 1 -a $FAST = 1 ]; then
		#       Download file in 4 thread and leave file on ftp site
		        echo "`date -u +%Y%m%d%T%Z`; $msgout lftp -d -c \"pget -n 4 ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
		        lftp -d -c "pget -n 4 ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"
		elif [ $KEEP = 0 -a $FAST -lt 2 ]; then
        #       Download file normally and delete file on ftp site, can
        #       only delete using get not pget, so multi thread is not
        #       available
		        echo "`date -u +%Y%m%d%T%Z`; $msgout lftp -d -c \"get -E ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
		        lftp -d -c "get -E ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"
        elif [ $KEEP = 1 -a $FAST = 2 ]; then
                 #       Download multiple file normally and leave file
                 #       on ftp site. mget does now allow multi thread.
                 echo "`date -u +%Y%m%d%T%Z`; $msgout lftp -d -c \"mget ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
                 lftp -d -c "mget ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"
        else 
                 # Not allowed
                 MSG="KEEP = $KEEP and FAST = $FAST are not allowed"
                 echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
                 cylc task-message -p CRITICAL $MSG
                 cylc task-failed
                 exit 1
		fi

		# Check for lftp errors
		result=$?
		case $result in
		        0)
                        if [ $FAST != 2 ]; then 
                            mv $FILENAME $FILEOUT
                            MSG="Moving file $FILENAME to $FILEOUT"
                            echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
                        fi
                        if [ $CHECKSUM = 1 ]; then
                            lftp -d -c "get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$CHECKFILE"
                            sum $FILENAME | sort > NIWA_$CHECKFILE                             
                            if diff NIWA_$CHECKFILE $CHECKFILE
                            then
                                MSG="File $FILENAME check sum OK"
                                echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
                                cylc task-message $MSG
                            else
                                MSG="File $FILENAME check sum failed"
                                 echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
                                 cylc task-message -p CRITICAL $MSG
                                 cylc task-failed
                                 exit 1
                            fi
                        fi
		                MSG="file $FILEOUT ready"
		                echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
		                cylc task-message $CYLC_MESSAGE
		                # SUCCESS MESSAGE
                        cylc task-finished
        				exit 0
		                ;;
		        *)
		                MSG="download $FILENAME from $SRCE to ${DEST_LOC} failed"
		                echo "`date -u +%Y%m%d%T%Z`; $msgout $MSG"
		                cylc task-message -p CRITICAL $MSG
                        cylc task-failed
		                exit 1
		                ;;
		esac
	else
        # If file not there yet, trying every minute until a $TIMEOUT
        # then stops
        n=$((n+1))
        echo "`date -u +%Y%m%d%T%Z`; $msgout Trying again (n=$n) to find $FILENAME file on $SRCE, be back in 1 minute"
        # Send Cylc and NAGIOS a critical message if file not found
        # after $TIMEOUT minutes
        if [ $n = $TIMEOUT ]; then
              MSG="$msgout $FILENAME on $SRCE has not been found yet in the past $TIMEOUT minutes."
              echo "`date -u +%Y%m%d%T%Z`; $MSG"
              # Send critical message and stop.
              cylc task-message -p CRITICAL $MSG
              $NAGIOS $SERVICE CRITICAL $MSG
              cylc task-failed
              exit 1
        fi
	    sleep 60
	fi
done
