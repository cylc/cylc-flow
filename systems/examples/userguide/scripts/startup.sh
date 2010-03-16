#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# oneoff startup task to clean out the system work space.

# run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# START MESSAGE
cylc message --started

mkdir -p $TMPDIR || \
{
    cylc message -p CRITICAL "failed to create $TMPDIR"
    cylc message --failed
    exit 1
}

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

echo "CLEANING $TMPDIR"
rm -rf $TMPDIR/* || \
{
    cylc message -p CRITICAL "failed to clean out $TMPDIR"
    cylc message --failed
    exit 1
}

# SUCCESS MESSAGE
cylc message --succeeded
