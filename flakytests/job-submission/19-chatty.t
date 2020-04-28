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
# Test job submission with a very chatty command.
# + Simulate "cylc jobs-submit" getting killed half way through.

. "$(dirname "$0")/test_header"

skip_darwin 'atrun hard to configure on Mac OS'

set_test_number 14

create_test_globalrc "
process pool timeout = PT10S" ""

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-suite-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"

# Logged killed jobs-submit command
cylc cat-log "${SUITE_NAME}" | sed -n '
/\[jobs-submit \(cmd\|ret_code\|out\|err\)\]/,+2{
    s/^.*\(\[jobs-submit\)/\1/p
}' >'log'
contains_ok 'log' <<'__OUT__'
[jobs-submit ret_code] -9
[jobs-submit err] killed on timeout (PT10S)
__OUT__

# Logged jobs that called talkingnonsense
sed -n 's/\(\[jobs-submit out\]\) .*\(|1\/\)/\1 \2/p' 'log' >'log2'
N=0
while read -r; do
    TAIL="${REPLY#${SUITE_RUN_DIR}/log/job/}"
    TASK_JOB="${TAIL%/job}"
    contains_ok 'log2' <<<"[jobs-submit out] |${TASK_JOB}|1|None"
    ((N += 1))
done <"${SUITE_RUN_DIR}/talkingnonsense.out"
# Logged jobs that did not call talkingnonsense
for I in $(eval echo "{$N..9}"); do
    contains_ok 'log2' <<<"[jobs-submit out] |1/nh${I}/01|1"
done

# Task pool in database contains the correct states
# Use LANG=C sort to put # on top
cylc ls-checkpoints "${SUITE_NAME}" '0' \
    | sed -n '/^# TASK POOL/,$p' \
    | sed '/^# TASK POOL/d' \
    | sort >'cylc-ls-checkpoints.out'

cmp_ok 'cylc-ls-checkpoints.out' <<'__OUT__'
1|h0|1|succeeded|0
1|h1|1|succeeded|0
1|h2|1|succeeded|0
1|h3|1|succeeded|0
1|h4|1|succeeded|0
1|h5|1|succeeded|0
1|h6|1|succeeded|0
1|h7|1|succeeded|0
1|h8|1|succeeded|0
1|h9|1|succeeded|0
1|nh0|0|submit-failed|0
1|nh1|0|submit-failed|0
1|nh2|0|submit-failed|0
1|nh3|0|submit-failed|0
1|nh4|0|submit-failed|0
1|nh5|0|submit-failed|0
1|nh6|0|submit-failed|0
1|nh7|0|submit-failed|0
1|nh8|0|submit-failed|0
1|nh9|0|submit-failed|0
1|starter|1|succeeded|0
1|stopper|1|succeeded|0
__OUT__

purge_suite "${SUITE_NAME}"
exit
