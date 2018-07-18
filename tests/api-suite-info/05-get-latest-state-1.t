#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

# Test "get_latest_state" API call, return keys in incremental mode.

json_keys_cmp() {
    # Load JSON from file in argumnet 1.
    # Return True if data structure is a dict containing all and only the keys
    # specified in the remaining arguments
    local TEST_KEY="$1"
    run_ok "${TEST_KEY}" python - "$@" <<'__PYTHON__'
import json
import sys
data = json.load(open(sys.argv[1]))
exp_keys = [unicode(arg) for arg in sys.argv[2:]]
exp_keys.sort()
act_keys = list(data.keys())
try:
    act_keys.remove('mean_main_loop_interval')  # unreliable
except ValueError:
    pass
act_keys.sort()
if exp_keys != act_keys:
    raise AssertionError(r'%s != %s' % (exp_keys, act_keys))
__PYTHON__
    if [[ -s "${TEST_KEY}.stderr" ]]; then
        cat "${TEST_KEY}.stderr" >&2
    fi
}

. "$(dirname "$0")/test_header"
set_test_number 15

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    cycle point time zone = Z
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = PT2M
[scheduling]
    initial cycle point = 2010
    final cycle point = 2012
    [[dependencies]]
        [[[P1Y]]]
            graph = foo[-P1Y] => foo => bar
[runtime]
    [[foo, bar]]
        script = true
__SUITERC__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

cylc run --hold "${SUITE_NAME}"
UUID="$(uuidgen)"

# Call 1, full
run_ok "${TEST_NAME_BASE}-1" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-1.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' 'err_content' \
    'err_size' 'full_mode' 'summary'
sleep 1
# Call 2, incremental
run_ok "${TEST_NAME_BASE}-2" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-2.stdout" 'cylc_version' 'full_mode'

# Run the 2010 tasks and wait
cylc release "${SUITE_NAME}" '2010/*'
cylc suite-state "${SUITE_NAME}" \
    --task='bar' --status='succeeded' --point='20100101T0000Z' \
    --interval=1 --max-polls=20

# Call 3, after some normal activities
sleep 1
run_ok "${TEST_NAME_BASE}-3" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-3.stdout" \
    'cylc_version' 'full_mode' 'summary'
sleep 1
# Call 4, incremental
run_ok "${TEST_NAME_BASE}-4" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-4.stdout" \
    'cylc_version' 'full_mode'

# Call 5, after a reload
cylc reload "${SUITE_NAME}"
LOG="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/log"
poll "! grep -qF 'Reload completed' '${LOG}'"
run_ok "${TEST_NAME_BASE}-5" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-5.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' \
    'full_mode' 'summary'
sleep 1
# Call 6, incremental
run_ok "${TEST_NAME_BASE}-6" \
    cylc client -n --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}"
json_keys_cmp "${TEST_NAME_BASE}-6.stdout" \
    'cylc_version' 'full_mode'

# Call 7, forced full mode
run_ok "${TEST_NAME_BASE}-7" \
    cylc client --set-uuid="${UUID}" 'get_latest_state' "${SUITE_NAME}" \
    <<<'{"full_mode": true}'
json_keys_cmp "${TEST_NAME_BASE}-7.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' 'err_content' \
    'err_size' 'full_mode' 'summary'

# Stop and purge the suite.
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
