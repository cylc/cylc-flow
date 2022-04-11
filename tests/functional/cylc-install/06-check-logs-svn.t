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

svn --version || skip_all "svn not installed"

set_test_number 3

WORKFLOW="$(date | md5sum | awk '{print $1}')"
WORKFLOW_NAME="$(workflow_id "${TEST_NAME_BASE}")"
WORKFLOW_RUN_DIR="${RUN_DIR}/${WORKFLOW_NAME}"
WORKDIR1="${PWD}/workdir1"

# Create a workflow in a subdirectory of the test tmpdir
mkdir -p "${WORKDIR1}/${WORKFLOW}"
cat > "${WORKDIR1}/${WORKFLOW}/flow.cylc" <<__HEREDOC__
[scheduler]
implicit tasks allowed = True
[scheduling]
    initial cycle point = 1649
    [[graph]]
        R1 = foo
__HEREDOC__

# Touch some non-functional files:
touch "${WORKDIR1}/${WORKFLOW}/test_file_in_workflow"
touch "${WORKDIR1}/test_file_outside_workflow"

# Create an SVN repo:
svnadmin create "myrepo"
svn import "${WORKDIR1}" "file:///${PWD}/myrepo/trunk" -m "foo"
svn co "file:///${PWD}/myrepo/trunk" "${PWD}/elephant"
cd "elephant" || exit

# Make changes since commit:
echo "Inside workflow" > "${WORKFLOW}/test_file_in_workflow"
echo "Outside workflow" > test_file_outside_workflow

# Carry out actual test:

run_ok "${TEST_NAME_BASE}-install" \
    cylc install "./${WORKFLOW}" --no-run-name --workflow-name "${WORKFLOW_NAME}"

DIFF_FILE="${WORKFLOW_RUN_DIR}/log/version/uncommitted.diff"
grep_ok "Inside workflow" "$DIFF_FILE"
grep_fail "Outside workflow" "$DIFF_FILE"

purge
