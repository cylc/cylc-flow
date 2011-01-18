#!/usr/bin/perl -w

while (<>) {
    s/trap \'cylc message --failed\'/trap 'cylc task-failed "error trapped"'/;
    s/cylc message --started/cylc task-started || exit 1/;
    next if s/cylc message --failed//;
    s/cylc message -p CRITICAL/cylc task-failed/;
    s/cylc message --succeeded/cylc task-finished/;
    s/cylc message/cylc task-message/;
    print;
}
