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
# Test workflow installation
. "$(dirname "$0")/test_header"
set_test_number 9

cat > flow.cylc <<__HEREDOC__
[scheduler]
    allow implicit tasks = true
[scheduling]
    [[graph]]
        R1 = foo
__HEREDOC__

run_ok "$TEST_NAME_BASE" cylc validate "$PWD"/flow.cylc

TEST_FOLDERS=()
MSG="Nested install directories not allowed"


TEST_FOLDER=cylctb-$(uuidgen)
TEST_FOLDERS+=("$TEST_FOLDER")
cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/"

TEST_NAME="${TEST_NAME_BASE}-child"
run_fail "$TEST_NAME" cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/child/grandchild"
grep_ok "$MSG" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}-child-no-run-name"
run_fail "$TEST_NAME" cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/child/grandchild" --no-run-name
grep_ok "$MSG" "${TEST_NAME}.stderr"


TEST_FOLDER=cylctb-$(uuidgen)
TEST_FOLDERS+=("$TEST_FOLDER")
cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/child/grandchild"

TEST_NAME="${TEST_NAME_BASE}-parent"
run_fail "$TEST_NAME" cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/"
grep_ok "$MSG" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}-parent-no-run-name"
run_fail "$TEST_NAME" cylc install -C "$PWD" --workflow-name "${TEST_FOLDER}/" --no-run-name
grep_ok "$MSG" "${TEST_NAME}.stderr"

# Cleanup all the test folders added to the array.
# shellcheck disable=SC2048
for TEST_FOLDER in ${TEST_FOLDERS[*]}; do
    rm -fr "${RUN_DIR}/${TEST_FOLDER:-}"
done

exit
