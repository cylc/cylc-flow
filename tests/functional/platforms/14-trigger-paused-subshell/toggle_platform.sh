#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

# Script that outputs the current platform written in the hall file and changes
# it to the other one. This ensures the platform subshell result will alternate
# each time it is called.

remote_platform=$1
hall_file="${CYLC_WORKFLOW_RUN_DIR}/pretend_hall_info"

if [[ ! -f "${hall_file}" ]]; then
    current=localhost
else
    current=$(cat "$hall_file")
fi

echo "$current"

if [[ "$current" == localhost ]]; then
    echo "$remote_platform" > "$hall_file"
else
    echo localhost > "$hall_file"
fi
