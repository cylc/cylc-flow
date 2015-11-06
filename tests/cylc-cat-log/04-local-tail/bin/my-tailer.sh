#!/bin/bash
# Modify 'tail' output to prove that cylc used the custom tailer.
# Exit immediately, for the test (i.e. don't 'tail -F')
FILE=$1
tail -n +1 $FILE | awk '{print "HELLO", $0; fflush() }'
