#!/bin/bash
FILE=$1
#tail -n +1 -F $FILE | awk '{print "HELLO>", $0; fflush() }'
tail -n +1 $FILE | awk '{print "HELLO", $0; fflush() }'
