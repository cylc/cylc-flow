#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"
AGENT="cylc/${CYLC_VERSION:-$(cylc --version)} prog_name/cylc-test-battery uuid/$(uuidgen)"

# Call 1, full, no "mean_main_loop_interval" as suite started on hold
run_ok "${TEST_NAME_BASE}-1" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-1.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' 'err_content' \
    'err_size' 'full_mode' 'summary'
# Call 2, incremental
run_ok "${TEST_NAME_BASE}-2" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-2.stdout" 'cylc_version' 'full_mode'

# Run the 2010 tasks and wait
cylc release "${SUITE_NAME}" '2010/*'
cylc suite-state "${SUITE_NAME}" \
    --task='bar' --status='succeeded' --point='20100101T0000Z' \
    --interval=1 --max-polls=20

# Call 3, after some normal activities
run_ok "${TEST_NAME_BASE}-3" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-3.stdout" \
    'cylc_version' 'full_mode' 'mean_main_loop_interval' 'summary'
# Call 4, incremental
run_ok "${TEST_NAME_BASE}-4" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-4.stdout" \
    'cylc_version' 'full_mode' 'mean_main_loop_interval'

# Call 5, after a reload
cylc reload "${SUITE_NAME}"
LOG="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/suite/log"
poll "! grep -qF 'Reload completed' '${LOG}'"
run_ok "${TEST_NAME_BASE}-5" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-5.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' \
    'full_mode' 'mean_main_loop_interval' 'summary'
# Call 6, incremental
run_ok "${TEST_NAME_BASE}-6" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state"
json_keys_cmp "${TEST_NAME_BASE}-6.stdout" \
    'cylc_version' 'full_mode' 'mean_main_loop_interval'

# Call 7, forced full mode
run_ok "${TEST_NAME_BASE}-7" \
    env no_proxy=* curl -A "${AGENT}" -v --cacert "${SRV_D}/ssl.cert" \
    --digest -u "cylc:$(<"${SRV_D}/passphrase")" \
    "https://${HOST}:${PORT}/get_latest_state?&full_mode=True"
json_keys_cmp "${TEST_NAME_BASE}-7.stdout" \
    'ancestors' 'ancestors_pruned' 'cylc_version' 'descendants' 'err_content' \
    'err_size' 'full_mode' 'mean_main_loop_interval' 'summary'

# Stop and purge the suite.
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
