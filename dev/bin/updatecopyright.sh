#!/bin/bash

set -e

# Automatically update copyright years; use once annually.
# USAGE:
# cd $CYLC_DIR
# find . -type f -not -path "./.*" | xargs dev/bin/updatecopyright
# (find path exclusion avoids .git directory!)

YY=$(date +%y)

#OLD="Copyright \(C\) 2008-20\d\d Hilary Oliver, NIWA"
#NEW="Copyright (C) 2008-20$YY Hilary Oliver, NIWA"
OLD="#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE."
NEW="#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE."

FILES=$@
for FILE in $FILES; do
    echo $FILE
    if [[ ! -f $FILE ]]; then
        echo "ERROR: no such file: $FILE"
        exit 1
    fi
    perl -pi -e "s/$OLD/$NEW/" $FILE
done
 
