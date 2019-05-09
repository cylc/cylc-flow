#!/bin/bash

set -e

# Automatically update copyright year - use once annually.

# USAGE:
#   % find . -type f -not -path "./.*" | xargs dev/bin/updatecopyright.sh
# ("./.*" avoids .git directory)

YY=$(date +%y)

OLD="Copyright \(C\) 2008-20\d\d NIWA & British Crown \(Met Office\) & Contributors."
NEW="Copyright (C) 2008-20$YY NIWA & British Crown (Met Office) & Contributors."

for FILE in "$@"; do
    echo "$FILE"
    if [[ ! -f $FILE ]]; then
        echo "ERROR: no such file: $FILE"
        continue
    fi
    perl -pi -e "s/$OLD/$NEW/" "$FILE"
done
