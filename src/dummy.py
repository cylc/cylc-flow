#!/usr/bin/env

# dummy mode task commands

dummy_command = 'cylc wrap -m "echo Hello from DUMMY $TASK_ID; sleep $CYLC_DUMMY_SLEEP"'
dummy_command_fail = 'cylc wrap -m "echo Hello from DUMMY ${TASK_ID}, ABORTING by request; /bin/false"'
