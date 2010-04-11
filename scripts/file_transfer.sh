#!/bin/bash

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|


# THIS IS A CYLC TASK SCRIPT

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# this is a cylc task utility script, meant to be WRAPPED by specific
# cylc tasks

# Purpose: file copy or transfer.

# Task-specific inputs:
#   1. $SRCE  -  list of space separated file URLs
#   2. $DEST  -  parallel list of space separated FILE URLs
#                (NOT DIRECTORY URLS - ALWAYS GIVE A FILENAME)

# This script is a multiple-call wrapper for 'scp' that takes
# its arguments from environment variables exported by cylon.

# As scp-style URLs SRCE and DEST can be prefixed with 'hostname:'.

# passwordless ssh must be configured for all transfers. 
# (but scp defaults to 'cp' for local copies?)

# Normally either the target or destination (or both) will be local,
# but note that scp supports copying between two remote platforms.

# The script lets scp decide if the target and destination are valid
# URLs. 

# TO DO: allow for unpacking at destination? (this is more difficult in
# some cases; imagine a tar archive of many compressed files).

if [[ -z $SRCE ]]; then
    cylc message -p CRITICAL "SRCE not defined"
    cylc message --failed
    exit 1
fi

if [[ -z $DEST ]]; then
    cylc message -p CRITICAL "DEST not defined"
    cylc message --failed
    exit 1
fi

for T in $SRCE; do
    # get destination corresponding to this target
    D=${DEST%% *}
    # remove this destination from the list of remaining destinations
    DEST=${DEST#* }

    cylc message "initiating file transfer from $T to $D"

    # check destination directory exists
    if [[ $D = *:* ]]; then
        # remote destination
        RMACH=${D%:*}
        RPATH=${D#*:}

        #RFILE=$( basename $RPATH )
        RDIR=$( dirname $RPATH )

        #cylc message "making remote destination directory, $RDIR"
        ssh $RMACH mkdir -p $RDIR
    else
        DIR=$( dirname $D )
        #cylc message "making destination directory, $DIR"
        mkdir -p $DIR
    fi

    scp -B $T $D > /dev/null

done
