#!/bin/bash

# Register the actual source example suites (not copies) 
# under a given a top level group name.

# Hilary Oliver, 2012

if [[ $# != 1 ]]; then
    echo "USAGE: $0 <TOP-LEVEL-GROUP-NAME>"
    exit 1
fi

TOP=$1

cd $( dirname $( which cylc ) )/../examples
pwd
for f in $(find * -name suite.rc); do 
    cylc db reg $( echo ${TOP}.$(dirname $f) | tr / .) $f
done

