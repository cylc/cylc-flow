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

#------------------------------------------------------------------------------
# Check that symlink is not resolved to its target on installation:
# When ~/foo -> ~/bar and --symlink-dirs=run=~/bar DO NOT make run=~/foo

. "$(dirname "$0")/test_header"
set_test_number 3

cat > flow.cylc <<__HEREDOC__
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = 1500
    [[graph]]
        R1 = foo
__HEREDOC__

run_ok "cylc validate ."

# Create a temporary directory to put our symlinked foo and bar in:
elsewhere=$(mktemp -d)
mkdir -p "${elsewhere}/foo"
ln -s "${elsewhere}/foo" "bar"

# Install the workflow:
run_ok "$TEST_NAME_BASE" cylc install --no-run-name --symlink-dirs=run="${elsewhere}/bar"

# Check the installed workflow:
ls -l "$RUN_DIR/$(basename "$PWD")" > list
grep_ok "bar\/cylc-run" list

# Tidy up:
cylc clean "$(basename "$PWD")" 2> /dev/null
rm -fr "${elsewhere}"

exit
