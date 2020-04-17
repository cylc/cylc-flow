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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Test authentication - privilege 'full-control' (with passphrase).

. "$(dirname "$0")/test_header"
set_test_number 12

API_VERSION="$(python -c 'from cylc.flow.network import API; print(API)')"

install_suite "${TEST_NAME_BASE}" 'basic'

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
# Set public auth low to test that passphrase gives full control
create_test_globalrc '' '
[authentication]
    public = identity'
cylc run "${SUITE_NAME}"
unset CYLC_CONF_PATH

# Wait for first task 'foo' to fail.
poll_grep 'CYLC_JOB_EXIT' "${SUITE_RUN_DIR}/log/job/1/foo/01/job.status"
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --point=1 \
    --interval=1 --max-polls=10 || exit 1

# Check scan --full output.
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"
PUBLISH_PORT="$(sed -n 's/^CYLC_SUITE_PUBLISH_PORT=//p' "${SRV_D}/contact")"
cylc scan --comms-timeout=10 -f --color=never -n "${SUITE_NAME}" >'scan-f.out'
cmp_ok 'scan-f.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT} ${USER}@${HOST}:${PUBLISH_PORT}
   Title:
      Authentication test suite.
   Description:
      Stalls when the first task fails.
      Here we test out a multi-line description!
   Group:
      (no Group)
   API:
      ${API_VERSION}
   URL:
      (no URL)
   another_metadata:
      1
   custom_metadata:
      something_custom
   Task state totals:
      failed:1 waiting:2
      1 failed:1 waiting:1
      2 waiting:1
__END__

# Check scan --describe output.
cylc scan --comms-timeout=10 -d --color=never -n "${SUITE_NAME}" >'scan-d.out'
cmp_ok 'scan-d.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT}
   Title:
      Authentication test suite.
   Description:
      Stalls when the first task fails.
      Here we test out a multi-line description!
   Group:
      (no Group)
   API:
      ${API_VERSION}
   URL:
      (no URL)
   another_metadata:
      1
   custom_metadata:
      something_custom
__END__

# Check scan --raw output.
cylc scan --comms-timeout=10 -f -t raw --color=never -n "${SUITE_NAME}" \
    >'scan-r.out'
cmp_ok 'scan-r.out' <<__END__
${SUITE_NAME}|${USER}|${HOST}|port|${PORT}|publish-port|${PUBLISH_PORT}
${SUITE_NAME}|${USER}|${HOST}|title|Authentication test suite.
${SUITE_NAME}|${USER}|${HOST}|description|Stalls when the first task fails. Here we test out a multi-line description!
${SUITE_NAME}|${USER}|${HOST}|group|
${SUITE_NAME}|${USER}|${HOST}|API|${API_VERSION}
${SUITE_NAME}|${USER}|${HOST}|URL|
${SUITE_NAME}|${USER}|${HOST}|another_metadata|1
${SUITE_NAME}|${USER}|${HOST}|custom_metadata|something_custom
${SUITE_NAME}|${USER}|${HOST}|states|failed:1 waiting:2
${SUITE_NAME}|${USER}|${HOST}|states:1|failed:1 waiting:1
${SUITE_NAME}|${USER}|${HOST}|states:2|waiting:1
__END__

# Check scan --json output.
cylc scan --comms-timeout=10 -f -t json --color=never -n "${SUITE_NAME}" \
    >'scan-j.out'
sed -i -r 's/[0-9\.]{10,}/"<FLOAT_REPLACED>"/' 'scan-j.out'
cmp_json 'scan-j.out' 'scan-j.out' <<__END__
[
    [
        "${SUITE_NAME}",
        "${HOST}",
        "${PORT}",
        "${PUBLISH_PORT}",
        "${API_VERSION}",
        {
            "version":"$(cylc version)",
            "states":[
                {
                    "failed":1,
                    "waiting":2
                },
                {
                    "1":{
                        "failed":1,
                        "waiting":1
                    },
                    "2":{
                        "waiting":1
                    }
                }
            ],
            "tasks-by-state":{
                "failed":[
                    [
                        "<FLOAT_REPLACED>",
                        "foo",
                        "1"
                    ]
                ],
                "waiting":[
                    [
                        0,
                        "pub",
                        "2"
                    ],
                    [
                        0,
                        "bar",
                        "1"
                    ]
                ]
            },
            "meta":{
                "group":"",
                "description":"Stalls when the first task fails.\nHere we test out a multi-line description!",
                "title":"Authentication test suite.",
                "URL":"",
                "another_metadata":"1",
                "custom_metadata":"something_custom"
            },
            "owner":"${USER}",
            "update-time":"<FLOAT_REPLACED>",
            "name":"${SUITE_NAME}"
        }
    ]
]
__END__

# "cylc show" (suite info) OK.
TEST_NAME="${TEST_NAME_BASE}-show1"
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log1
grep_ok "\\[client-command\\] get_suite_info ${USER}@.*cylc-show" 'suite.log1'

# "cylc show" (task info) OK.
TEST_NAME="${TEST_NAME_BASE}-show2"
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}" foo
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\\[client-command\\] get_task_info ${USER}@.*cylc-show" 'suite.log2'

# Commands OK.
# (Reset to same state).
TEST_NAME="${TEST_NAME_BASE}-trigger"
run_ok "${TEST_NAME}" cylc reset "${SUITE_NAME}" -s failed foo 1
cylc log "${SUITE_NAME}" > suite.log3
grep_ok "\\[client-command\\] reset_task_states ${USER}@.*cylc-reset" 'suite.log3'

# Shutdown and purge.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_ok "${TEST_NAME}" cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
