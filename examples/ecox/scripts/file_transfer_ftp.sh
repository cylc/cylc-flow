#!/bin/bash
# Generic file(s) ftp download
# Requires .netrc file to be set up to allow automatic ftp server login
#
# This is a cylc wrapped script
#
# Author: Bernard Miville
# Date: 26 August 2010
#
# Environment variables:
#   1. SRCE         - Source ftp server address
#   2. SRCE_LOC     - path at the source
#   3. DEST_LOC     - path at the destination (Assuming the destination is on the same server as the request)
#   4. FILENAME     - name of file to transfer
#   5. SRCE_USER    - username at the source (password assumed to be in .netrc file)   
#   6. SERVICE      - SERVICE name for NAGIOS
#   7. KEEP         - 0 delete file from ftp site
#                     1 leave file on ftp site
#   8. FAST         - 0 download single file single thread
#                     1 download single file 4 threads
#                     2 Download multiple files single thread
#                     3 Download multiple files 4 threads
#   9. FILEOUT      - Destination file name. Not used if downloading
#                     multiple files.
#                     downloads multiple files and do not rename them
#   10. TIMEOUT     - Number of minutes to try finding the file
#   11. CHECKSUM    - 0 do not do a check sum 
#                     1 do a check sum and compare with downloaded check sum file
#   12. CHECKFILE   - Name of downloaded check sum file (optional, only required
#                     if $CHECKSUM=1)
#

# Trap errors so that we need not check the success of basic operations.
set -e

# Parameters
SYSTEM=${USER##*_}
. /$SYSTEM/ecoconnect/ecoconnect_$SYSTEM/bin/ecfunctions.sh
PROG=`basename $0`
msgout="CYCLE_TIME:${CYCLE_TIME}; SCRIPT:${PROG};"
MSG="`date -u +%Y%m%d" "%T" "%Z`; $msgout Started"
echo "$MSG"
n=0

# Print environment variables list
echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Arguments list:"
echo "   1-  SRCE:         ${SRCE}"
echo "   2-  SRCE_LOC:     ${SRCE_LOC}"
echo "   3-  DEST_LOC:     ${DEST_LOC}"
echo "   4-  FILENAME:     ${FILENAME}"
echo "   5-  SRCE_USER:    ${SRCE_USER}"
echo "   6-  SERVICE:      ${SERVICE}"
echo "   7-  KEEP:         ${KEEP}"
echo "   8-  FAST:         ${FAST}"
echo "   9-  FILEOUT:      ${FILEOUT}"
echo "   10- TIMEOUT:      ${TIMEOUT}"
echo "   11- CHECKSUM:     ${CHECKSUM}"
echo "   12- CHECKFILE:    ${CHECKFILE}"

# Check the environment variables
# Directories
cylcutil check-vars -d DEST_LOC
# Variables
cylcutil check-vars SRCE \
                    SRCE_LOC \
                    FILENAME \
                    SRCE_USER \
                    SERVICE \
                    KEEP \
                    FAST \
                    FILEOUT \
                    TIMEOUT \
                    CHECKSUM \
                    CHECKFILE

if [ $FAST -gt 3 -o $FAST -lt 0 ]; then
	MSG="FAST is not within allowed range (0,1,2,3)"
	echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
	cylc task-message -p CRITICAL $MSG
	exit 1
fi

if [ $KEEP -gt 1 -o $KEEP -lt 0 ]; then
	MSG="KEEP is not within allowed range (0,1)"
	echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
	cylc task-message -p CRITICAL $MSG
	exit 1
fi

if [ $CHECKSUM -gt 1 -o $CHECKSUM -lt 0 ]; then
	MSG="CHECKSUM is not within allowed range (0,1)"
	echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
	cylc task-message -p CRITICAL $MSG
	exit 1
fi

# Send NAGIOS OK message
$NAGIOS $SERVICE OK $msgout

# Grep does not always like the wildcard *, it uses . instead in
# combination with *
# So for multiple files download, we change the wildcard to fit grep
FILEGREP=`echo $FILENAME | sed -e "s/\*/.\*/g"`

# ~/ as root directory does not work with lfpt 
if [ $SRCE_LOC = '/' -o $SRCE_LOC = '~/' ]; then
	SRCE_LOC=""
fi

# Check if file is there and download it
while true; do
	# Getting listing of all files to verify if wanted files is actually
	# there. For EcoConnect, if this script is invoked, it is because the
	# file has been confirmed to be on the ftp site.
	# Note: recls can be used with a pattern to list only files you
	# want. This is not used here as we use grep instead (see below).
	# Try connecting 5 times to ftp site (in case it is down the first
	# time). Stop trying after 5 minutes and send alert.
	echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Getting listing of files on ${SRCE}${SRCE_LOC}"
	result=0
	for a in {1..5}; do
		if ! testfile=$(lftp -c open -e "recls -1" ftp://${SRCE_USER}@${SRCE}/${SRCE_LOC}); then
			result=1
			MSG="Could not connect on attempt number $a to source: $SRCE"
			echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
			cylc task-message -p WARNING $MSG
			# Wait 60 seconds before trying again
			sleep 60
		else
			echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Download files listing from $SRCE was successful"
			break;
		fi
	done
	if [ ! $result -eq 0 ]; then
		MSG="$msgout Connection failed $a times to $SRCE"
		echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
		$NAGIOS $SERVICE CRITICAL $MSG
		cylc task-message -p CRITICAL $MSG
		exit 1
	fi
	# Download file if there
	echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Trying to download $FILENAME from $SRCE"
	# First make sure the file is in the listing. If not there, it will
	# try again until the TIMEOUT.
	# A grep will exit with 0 if it finds the $FILENAME and 1 if it does
	# not find it. The "if" is used to avoid an exit failure trap by
	# cylc.
	if testgrep=$(echo "$testfile" | grep "$FILEGREP"); then
		echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Found file $FILENAME at $SRCE"
		# Start downloading
		MSG="initiating file transfer for $FILENAME from $SRCE to ${DEST_LOC}"
		cylc task-message $MSG
		MSG="Downloading $FILENAME from $SRCE ${SRCE_LOC} to ${DEST_LOC}"
		echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
		cd $DEST_LOC
		result=0
		# Try 5 tmies again to download file. In case connection was down on first try.
		for a in {1..5}; do
			if [ $KEEP = 1 -a $FAST = 0 ]; then
				# Download file normally and leave it on ftp site
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout lftp -d -c \"get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
				if ! lftp -d -c "get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"; then
    				result=1
				fi
				elif [ $KEEP = 1 -a $FAST = 1 ]; then
					# Download file in 4 threads and leave file on ftp site
					echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout lftp -d -c \"pget -n 4 ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
				if ! lftp -d -c "pget -n 4 ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"; then
                    result=1
				fi
			elif [ $KEEP = 0 -a $FAST -lt 2 ]; then
				# Download file normally and delete file on ftp site, can
				# only delete using get not pget, so multi thread is not
				# available.
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout lftp -d -c \"get -E ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
				if ! lftp -d -c "get -E ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"; then
    			    result=1
				fi
			elif [ $KEEP = 1 -a $FAST = 2 ]; then
		        	# Download multiple file normally and leave file
				# on ftp site. mget does now allow multi thread.
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout lftp -d -c \"mget ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME\""
				if ! lftp -d -c "mget ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$FILENAME"; then
    				result=1
				fi
			elif [ $KEEP = 1 -a $FAST = 3 ]; then
				# Download multiple file with 4 threads and leave files
				# on site.
				# Loop for all files
				echo -e "open ${SRCE}" > lftp_${FILENAME}.txt
				echo -e "cd ${SRCE_LOC}" >> lftp_${FILENAME}.txt
				for grepfile in $testgrep; do
					echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Preparing $grepfile from ${SRCE}${SRCE_LOC}"
					echo -e "pget -n 4 $grepfile" >> lftp_${FILENAME}.txt
				done
				echo -e "close" >> lftp_${FILENAME}.txt
				echo -e "quit" >> lftp_${FILENAME}.txt
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Starting multithread (pget -n 4) download of ${FILENAME} from ${SRCE}${SRCE_LOC}"
				if ! lftp -f lftp_${FILENAME}.txt; then
    				result=1
				fi
				rm lftp_${FILENAME}.txt
			else 
				# Not allowed
				MSG="KEEP = $KEEP and FAST = $FAST are not allowed"
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
				cylc task-message -p CRITICAL $MSG
				exit 1
			fi
			if [ ! $result -eq 0 ]; then
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Connection attempt number $a to $SRCE failed. Trying again in 1 minute"
				sleep 60
			else
				result=0
				break
			fi
		done
		# Check for lftp errors
		case $result in
		0)
			if [ $FAST -lt 2 ]; then 
                if [ "$FILEOUT" != "$FILENAME" ]; then
                    mv $FILENAME $FILEOUT
                fi
				MSG="Moving file $FILENAME to $FILEOUT"
				echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
			fi
			if [ $CHECKSUM = 1 ]; then
				# Get check sum file
				if ! lftp -d -c "get ftp://${SRCE_USER}@$SRCE${SRCE_LOC}/$CHECKFILE"; then
					MSG="download $CHECKFILE from $SRCE to ${DEST_LOC} failed"
					echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
					cylc task-message -p CRITICAL $MSG
					exit 1
				fi
				sum ${FILEOUT} | sort > NIWA_${CHECKFILE}
				cat ${CHECKFILE} | sort > UKMO_${CHECKFILE}
				if diff NIWA_${CHECKFILE} UKMO_${CHECKFILE}; then
			                rm NIWA_${CHECKFILE} ${CHECKFILE} UKMO_${CHECKFILE}
					MSG="File $FILEOUT check sum OK"
					echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
					cylc task-message $MSG
				else
					MSG="File $FILEOUT check sum failed"
					echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
					cylc task-message -p CRITICAL $MSG
					exit 1
				fi
			fi
			MSG="file $FILEOUT ready"
			echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
			exit 0
			;;
		*)
			MSG="Connection or download $FILENAME from $SRCE to ${DEST_LOC} failed"
			echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout $MSG"
			NAGIOS $SERVICE CRITICAL $MSG
			cylc task-message -p CRITICAL $MSG
			exit 1
			;;
		esac
	else
		# If file not there yet, trying every minute until a $TIMEOUT
		# then stops
		n=$((n+1))
		echo "`date -u +%Y%m%d" "%T" "%Z`; $msgout Trying again (n=$n) to find $FILENAME file on $SRCE, be back in 1 minute"
		# Send Cylc and NAGIOS a critical message if file not found
		# after $TIMEOUT minutes
		if [ $n = $TIMEOUT ]; then
			MSG="$msgout $FILENAME on $SRCE has not been found yet or connection failed in the past $TIMEOUT minutes."
			echo "`date -u +%Y%m%d" "%T" "%Z`; $MSG"
			# Send critical message and stop.
			$NAGIOS $SERVICE CRITICAL $MSG
			cylc task-message -p CRITICAL $MSG
			exit 1
		fi
		sleep 60
	fi
done
