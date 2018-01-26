#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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

. $(dirname $0)/test_header
set_test_number 12

install_suite "${TEST_NAME_BASE}" basic

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
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --point=1 \
    --interval=1 --max-polls=10 || exit 1

# Check scan --full output.
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"
cylc scan --comms-timeout=5 -fb -n "${SUITE_NAME}" >'scan-f.out' 2>'/dev/null'
cmp_ok 'scan-f.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT}
   Title:
      "Authentication test suite."
   Group:
      (no group)
   Description:
      "Stalls when the first task fails.
       Here we test out a multi-line description!"
   URL:
      (no URL)
   another_metadata:
      "1"
   custom_metadata:
      "something_custom"
   Task state totals:
      failed:1 waiting:2
      1 failed:1 waiting:1
      2 waiting:1
__END__

# Check scan --describe output.
cylc scan --comms-timeout=5 -db -n "${SUITE_NAME}" >'scan-d.out' 2>'/dev/null'
cmp_ok 'scan-d.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT}
   Title:
      "Authentication test suite."
   Group:
      (no group)
   Description:
      "Stalls when the first task fails.
       Here we test out a multi-line description!"
   URL:
      (no URL)
   another_metadata:
      "1"
   custom_metadata:
      "something_custom"
__END__

# Check scan --raw output.
cylc scan --comms-timeout=5 -rb -n "${SUITE_NAME}" >'scan-r.out' 2>'/dev/null'
cmp_ok 'scan-r.out' <<__END__
${SUITE_NAME}|${USER}|${HOST}|port|${PORT}
${SUITE_NAME}|${USER}|${HOST}|another_metadata|1
${SUITE_NAME}|${USER}|${HOST}|custom_metadata|something_custom
${SUITE_NAME}|${USER}|${HOST}|description|Stalls when the first task fails. Here we test out a multi-line description!
${SUITE_NAME}|${USER}|${HOST}|title|Authentication test suite.
${SUITE_NAME}|${USER}|${HOST}|states|failed:1 waiting:2
${SUITE_NAME}|${USER}|${HOST}|states:1|failed:1 waiting:1
${SUITE_NAME}|${USER}|${HOST}|states:2|waiting:1
__END__

# Check scan --json output.
cylc scan --comms-timeout=5 -jb -n "${SUITE_NAME}" >'scan-j.out' 2>'/dev/null'
cmp_json_ok 'scan-j.out' 'scan-j.out' <<__END__
[
    [
        "${HOST}",
        "${PORT}",
        {
            "group":"",
            "description":"Stalls when the first task fails.\n                     Here we test out a multi-line description!",
            "title":"Authentication test suite.",
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
                "description":"Stalls when the first task fails.\n                     Here we test out a multi-line description!",
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
grep_ok "\[client-command\] get_suite_info ${USER}@.*:cylc-show" suite.log1

# "cylc show" (task info) OK.
TEST_NAME="${TEST_NAME_BASE}-show2"
run_ok "${TEST_NAME}" cylc show "${SUITE_NAME}" foo
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\[client-command\] get_task_info ${USER}@.*:cylc-show" suite.log2

# Commands OK.
# (Reset to same state).
TEST_NAME="${TEST_NAME_BASE}-trigger"
run_ok "${TEST_NAME}" cylc reset "${SUITE_NAME}" -s failed foo 1
cylc log "${SUITE_NAME}" > suite.log3
grep_ok "\[client-command\] reset_task_states ${USER}@.*:cylc-reset" suite.log3

# Shutdown and purge.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_ok "${TEST_NAME}" cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
