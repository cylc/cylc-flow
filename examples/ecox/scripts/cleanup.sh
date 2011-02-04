#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# Purpose: directory cleanup.
# Remove files under a given directory that are older 
# (by cycle time) than a given reference time cutoff. 

# Task-specific input:
#   1. $CLEANUP_DIRS     directories to clean
#   2. $CLEANUP_MATCH    find-style filename match pattern
#   3. $CLEANUP_CUTOFF   cycle time cutoff (delete older) 

if [[ -z $CLEANUP_DIRS ]]; then
	cylc message -p CRITICAL "CLEANUP_DIRS not defined"
    cylc message --failed
	exit 1
fi

if [[ -z $CLEANUP_MATCH ]]; then
	cylc message -p CRITICAL "CLEANUP_MATCH not defined"
    cylc message --failed
	exit 1
fi

if [[ -z $CLEANUP_CUTOFF ]]; then
	cylc message -p CRITICAL "CLEANUP_CUTOFF not defined"
    cylc message --failed
	exit 1
fi

cylc message "deleting $CLEANUP_MATCH older than $CLEANUP_CUTOFF under $CLEANUP_DIRS"
echo "deleting $CLEANUP_MATCH older than $CLEANUP_CUTOFF under $CLEANUP_DIRS"

# find files, and sort for cleaner output
FILENAMES=$( find $CLEANUP_DIRS -type f -name "$CLEANUP_MATCH" -print | sort )

for FILENAME in $FILENAMES; do

	# Extract FIRST cycle time from filename
	# METHOD: replace non-digit characters with spaces, then
	# count the number of digits in each resulting digit string
	RT=""
	for STR in $( echo $FILENAME | sed -e 's/[^0-9]/ /g' ); do
		if [[ $( echo -n $STR | wc -c ) = 10 ]]; then
			RT=$STR
			break
		fi
	done
	if [[ -z $RT ]]; then
		echo "WARNING: no cycle time found in $FILENAME"
		continue
	fi

    # delete if older than the cutoff
	if [[ $RT < $CLEANUP_CUTOFF ]]; then
		echo "deleting $FILENAME"
        rm $FILENAME
	fi
done

cylc message --succeeded
