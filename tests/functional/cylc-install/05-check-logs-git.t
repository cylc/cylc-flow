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
# Test that we only log version control info on workflow source dir
# when it is a subdir of a repo.

. "$(dirname "$0")/test_header"

if ! command -v 'git' > /dev/null; then
    skip_all 'git not installed'
fi
# set_test_number 6
set_test_number 3

WORKFLOW="$(date | md5sum | awk '{print $1}')"
WORKFLOW_NAME="$(workflow_id "${TEST_NAME_BASE}")"
WORKFLOW_RUN_DIR="${RUN_DIR}/${WORKFLOW_NAME}/runN"

# Create a workflow in a subdirectory of the test tmpdir
mkdir "${WORKFLOW}"
cat > "${WORKFLOW}/flow.cylc" <<__HEREDOC__
[scheduler]
implicit tasks allowed = True
[scheduling]
    initial cycle point = 1649
    [[graph]]
        R1 = foo
__HEREDOC__

# Touch some non-functional files
touch "${WORKFLOW}/test_file_in_workflow"
touch test_file_outside_workflow

# Initialize PWD as a git repo
git init .
git add .
git commit -m "commit 0"

# Make changes since commit:
echo "Inside workflow" > "${WORKFLOW}/test_file_in_workflow"
echo "Outside workflow" > test_file_outside_workflow

# Carry out actual test with relpath:
run_ok "${TEST_NAME_BASE}-install" \
    cylc install "./${WORKFLOW}" --workflow-name "${WORKFLOW_NAME}"
DIFF_FILE="${WORKFLOW_RUN_DIR}/log/version/uncommitted.diff"
grep_ok "Inside workflow" "$DIFF_FILE"
grep_fail "Outside workflow" "$DIFF_FILE"

purge
