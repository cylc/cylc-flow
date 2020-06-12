#!/bin/bash
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test restart from a checkpoint before a reload
. "$(dirname "$0")/test_header"
set_test_number 8
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

test_dump() {
    local TEST_NAME="$1"
    run_ok "${TEST_NAME}" python3 - "$@" <<'__PYTHON__'
import ast
import sys

data = ast.literal_eval(open(sys.argv[1]).read())
keys = list(sorted(data[1].keys()))
if keys != ["t1.2031", "t1.2032", "t2.2031", "t2.2032"]:
    sys.exit(keys)
for datum in data[1].values():
    assert isinstance(datum["mean_elapsed_time"], float)
__PYTHON__
}

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

RUND="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --debug --no-detach
suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --until=2028 --debug --no-detach
sed -n '/LOADING task run times/,+2{s/^.* INFO - //;s/[0-9]\(,\|$\)/%d\1/g;p}' \
    "${RUND}/log/suite/log" >'restart-1.out'
contains_ok 'restart-1.out' <<'__OUT__'
LOADING task run times
+ t2: %d,%d,%d,%d,%d
+ t1: %d,%d,%d,%d,%d
__OUT__
suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart "${SUITE_NAME}" --until=2030 --debug --no-detach
sed -n '/LOADING task run times/,+2{s/^.* INFO - //;s/[0-9]\(,\|$\)/%d\1/g;p}' \
    "${RUND}/log/suite/log" >'restart-2.out'
contains_ok 'restart-2.out' <<'__OUT__'
LOADING task run times
+ t2: %d,%d,%d,%d,%d,%d,%d,%d,%d,%d
+ t1: %d,%d,%d,%d,%d,%d,%d,%d,%d,%d
__OUT__
suite_run_ok "${TEST_NAME_BASE}-restart-3" \
    cylc restart "${SUITE_NAME}" --until=2031 --hold
# allow the task pool to settle before requesting a dump
cylc suite-state "${SUITE_NAME}" \
    --task=t1 \
    --point=2031 \
    --status=running \
    --interval=1 \
    --max-polls=10 1>'/dev/null' 2>&1
cylc dump -r "${SUITE_NAME}" >'cylc-dump.out'
test_dump 'cylc-dump.out'

cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
