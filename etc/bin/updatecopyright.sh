#!/bin/bash

set -e

# Automatically update copyright years; use once annually.
# USAGE:
# cd $CYLC_DIR
# find . -type f -not -path "./.*" | xargs dev/bin/updatecopyright.sh
# (find path exclusion avoids .git directory)

YY=$(date +%y)

OLD="Copyright \(C\) 2008-20\d\d NIWA"
NEW="Copyright (C) 2008-20$YY NIWA"

FILES=$@
for FILE in $FILES; do
    echo $FILE
    if [[ ! -f $FILE ]]; then
        echo "ERROR: no such file: $FILE"
        exit 1
    fi
    perl -pi -e "s/$OLD/$NEW/" $FILE
done
