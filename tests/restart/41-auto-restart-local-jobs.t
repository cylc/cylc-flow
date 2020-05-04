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
. "$(dirname "$0")/test_header"
CYLC_TEST_HOST2="$( \
    cylc get-global-config -i '[test battery]remote host with shared fs' \
    2>'/dev/null')"
if [[ -z "${CYLC_TEST_HOST2}" ]]; then
    skip_all '"[test battery]remote host with shared fs": not defined'
fi
export CYLC_TEST_HOST2
export CYLC_TEST_HOST1="${HOSTNAME}"
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
set_test_number 17

BASE_GLOBALRC="
[cylc]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
"

TEST_DIR="$HOME/cylc-run/" init_suite "${TEST_NAME_BASE}" <<< '
[scheduling]
    [[graph]]
        R1 = foo => bar => baz
[runtime]
    [[root]]
        script = sleep 15
'

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST1}
"

job-ps-line() {
    # line to grep for in ps listings to see if cylc background jobs are
    # running
    printf '/bin/bash.*log/job/1/%s/.*/job' "$1"
}

cylc run "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# auto stop-restart - normal mode:
#     ensure the suite WAITS for local jobs to complete before restarting
TEST_NAME="${TEST_NAME_BASE}-normal-mode"

cylc suite-state "${SUITE_NAME}" --task='foo' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

# ensure that later tests aren't placebos
run_ok "${TEST_NAME}-ps-1" ps -fu "${USER}"
grep_ok "$(job-ps-line foo)" "${TEST_NAME}-ps-1.stdout"

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST1}, ${CYLC_TEST_HOST2}
    condemned hosts = ${CYLC_TEST_HOST1}
"

FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-stop" "${FILE}" 40 1 \
    'The Cylc suite host will soon become un-available' \
    'Waiting for jobs running on localhost to complete' \
    'Waiting for jobs running on localhost to complete' \
    'Suite shutting down - REQUEST(NOW-NOW)' \
    "Attempting to restart on \"${CYLC_TEST_HOST2}\"" \
    "Suite now running on \"${CYLC_TEST_HOST2}\"" \

run_ok "${TEST_NAME}-ps-2" ps -fu "${USER}"
grep_fail "$(job-ps-line foo)" "${TEST_NAME}-ps-2.stdout"
grep_fail "$(job-ps-line bar)" "${TEST_NAME}-ps-2.stdout"

poll_suite_stopped
FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-restart" "${FILE}" 20 1 \
    "Suite server: url=tcp://$(get_fqdn_by_host "${CYLC_TEST_HOST2}")"
sleep 1
#-------------------------------------------------------------------------------
# auto stop-restart - force mode:
#     ensure the suite DOESN'T WAIT for local jobs to complete before stopping
TEST_NAME="${TEST_NAME_BASE}-force-mode"

cylc suite-state "${SUITE_NAME}" --task='bar' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST1}, ${CYLC_TEST_HOST2}
    condemned hosts = ${CYLC_TEST_HOST2}!
"

log_scan "${TEST_NAME}-stop" "${FILE}" 40 1 \
    'The Cylc suite host will soon become un-available' \
    'This suite will be shutdown as the suite host is unable to continue' \
    'Suite shutting down - REQUEST(NOW)' \

run_ok "${TEST_NAME}-ps-2" ssh "${CYLC_TEST_HOST2}" ps -fu "${USER}"
grep_ok "$(job-ps-line bar)" "${TEST_NAME}-ps-2.stdout"

cylc stop "${SUITE_NAME}" --now --now 2>/dev/null
poll_suite_stopped
sleep 1
purge_suite "${SUITE_NAME}"
