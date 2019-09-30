#!/bin/bash

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
