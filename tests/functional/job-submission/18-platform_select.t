#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test recovery of a failed host select command for a group of tasks.
. "$(dirname "$0")/test_header"
set_test_number 5

create_test_global_config "
[platforms]
    [[test platform]]
        hosts = localhost

    [[improbable platform name]]
        hosts = localhost
"

install_suite "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"

declare -A GREP_TESTS

# Check that we are warned that platform check will not occur until job-submit
GREP_TESTS["warn can't check at validate"]="""
    WARNING - Cannot attempt check .*platform_subshell.*\$(echo \"improbable platform name\")
"""

# Check that host = $(hostname) is correctly evaluated
GREP_TESTS["host subshell evaluate ok"]="""
    DEBUG - for task platform_subshell.1.*evaluated as improbable platform name
"""

# Check that platform = $(echo "improbable platform name") correctly evaluated
GREP_TESTS["platform subshell evaluate ok"]="""
    DEBUG - for task platform_subshell.1.*evaluated as improbable platform name
"""

for testname in "${!GREP_TESTS[@]}"; do
    # Symlink to get a better test name from grep_ok
    ln -s "${SUITE_RUN_DIR}/log/suite/log" "$testname"
    grep_ok "${GREP_TESTS[$testname]}" "$testname"
done

purge_suite "${SUITE_NAME}"

exit
