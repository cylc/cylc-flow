#!/bin/bash

set -e  # abort on error

# source sequenz environment
. $SEQUENZ_ENV

trap 'task-message CRITICAL failed' ERR

# INPUT:
# * no commandline arguments (for qsub)
# * environment variables:
#   1. $REFERENCE_TIME
#   2. $TASK_NAME      
#   3. $SEQUENZ_ENV
#   4. $CLEANUP_DIRS     directories to clean
#   5. $CLEANUP_MATCH    find-style filename match pattern
#   6. $CLEANUP_CUTOFF   reference time cutoff (delete older) 


# remove files under a given directory that are older (by reference
# time) than a given reference time cutoff. 

task-message NORMAL started

if [[ -z $REFERENCE_TIME ]]; then
	task-message CRITICAL "REFERENCE_TIME not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $TASK_NAME ]]; then
	task-message CRITICAL "TASK_NAME not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $CLEANUP_DIRS ]]; then
	task-message CRITICAL "CLEANUP_DIRS not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $CLEANUP_MATCH ]]; then
	task-message CRITICAL "CLEANUP_MATCH not defined"
    task-message CRITICAL failed
	exit 1
fi

if [[ -z $CLEANUP_CUTOFF ]]; then
	task-message CRITICAL "CLEANUP_CUTOFF not defined"
    task-message CRITICAL failed
	exit 1
fi

task-message NORMAL "deleting $CLEANUP_MATCH older than $CLEANUP_CUTOFF under $CLEANUP_DIRS"

# find files, and sort for cleaner output
FILENAMES=$( find $CLEANUP_DIRS -type f -name "$CLEANUP_MATCH" -print | sort )

for FILENAME in $FILENAMES; do

	# Extract FIRST reference time from filename
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
		echo "WARNING: no reference time found in $FILENAME"
		continue
	fi

    # delete if older than the cutoff
	if [[ $RT < $CLEANUP_CUTOFF ]]; then
		echo "deleting $FILENAME"
        rm $FILENAME
	fi
done

task-message NORMAL finished
