#!/bin/bash

# A cylc task event hook script that sends an email when called. 

# To get an email when any task in your suite fails, for example:
#________________________________________________
# (SUITE.RC)
# task failed hook script = cylc-email-alert.sh
#________________________________________________

# Cylc calls event hook scripts with the following arguments:
# EVENT SUITE TASK CYCLETIME  MESSAGE
# See the Cylc User Guide Suite.rc Reference for more information.

EVENT=$1      # e.g. "failed"
SUITE=$2      # group:name of the [failed] task
TASK=$3       # name of the [failed] task 
CTIME=$4      # cycle time of the [failed] task
MESSAGE="$5"  # quotes required (message contains spaces)

MAIL_SUBJECT="!!cylc alert!! $SUITE $TASK%$CTIME $EVENT" 
MAIL_ADDRESS=${MAIL_ADDRESS:-$USER@$HOSTNAME}
MAIL_BODY="SUITE: $SUITE
TASK: $TASK%$CTIME
MESSAGE: $MESSAGE"

echo "$MAIL_BODY" | mail -s "$MAIL_SUBJECT" $MAIL_ADDRESS
