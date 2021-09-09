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
# Test that we only log version control info on workflow.

. "$(dirname "$0")/test_header"
set_test_number 2

WORKFLOW=$(date | md5sum | awk '{print $1}')
RUN_DIR="${HOME}/cylc-run/${WORKFLOW}"


# Create a workflow in a subdirectory of the test tmpdir
mkdir ${WORKFLOW}
cat > ${WORKFLOW}/flow.cylc <<__HEREDOC__
[scheduler]
implicit tasks allowed = True
[scheduling]
    initial cycle point = 1649
    [[graph]]
        R1 = foo
__HEREDOC__

# Touch some non-functional files
touch ${WORKFLOW}/test_file_in_workflow
touch test_file_outside_workflow

# Initialize PWD as a git repo
git init .
git add .
git commit -m "commit 0"

# Make changes since commit:
echo "Inside workflow" > ${WORKFLOW}/test_file_in_workflow
echo "Outside workflow" > test_file_outside_workflow

# Carry out actual test:
cylc install -C "$PWD/${WORKFLOW}" --no-run-name
named_grep_ok "File inside flow VC'd" "Inside workflow" "${RUN_DIR}/log/version/uncommitted.diff"
grep_fail "Outside workflow" "${RUN_DIR}/log/version/uncommitted.diff"

# Clean up installed flow:
rm -fr "${RUN_DIR}"
