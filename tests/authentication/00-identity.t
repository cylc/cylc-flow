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

# Test authentication - privilege 'identity'.

. "$(dirname "$0")/test_header"
set_test_number 17

install_suite "${TEST_NAME_BASE}" basic

TEST_NAME="${TEST_NAME_BASE}-validate"
#TODOrun_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
create_test_globalrc '' '
[authentication]
    public = identity'
cylc run "${SUITE_NAME}"
unset CYLC_CONF_PATH

SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"

skip 2 'anon auth not supported'  # TODO
#run_ok "${TEST_NAME_BASE}-client-anon" \
#    cylc client -n --host="${HOST}" --port="${PORT}" 'identify'
#run_ok "${TEST_NAME_BASE}-client-anon.stdout" \
#    grep -qF "\"name\": \"${SUITE_NAME}\"" "${TEST_NAME_BASE}-client-anon.stdout"

TEST_NAME="${TEST_NAME_BASE}-client-cylc"
run_ok "${TEST_NAME}" \
    cylc client -n --host="${HOST}" --port="${PORT}" "${SUITE_NAME}" 'identify'
cmp_json "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" -c2 <<__JSON__
    {"name": "${SUITE_NAME}"}
__JSON__

TEST_NAME="${TEST_NAME_BASE}-client-cylc-bad-ping-task"
run_ok "${TEST_NAME}" cylc client "${SUITE_NAME}" 'ping_task' <<'__JSON__'
    {"task_id": "elephant.1", "exists_only": true}
__JSON__
cmp_json "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" <<'__JSON__'
    [false, "task not found"]
__JSON__

TEST_NAME="${TEST_NAME_BASE}-client-cylc-ping-task"
run_ok "${TEST_NAME}" cylc client "${SUITE_NAME}" 'ping_task' <<'__JSON__'
    {"task_id": "foo.1", "exists_only": true}
__JSON__
cmp_json "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" <<'__JSON__'
    [true, "task found"]
__JSON__

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --point=1 \
    --interval=1 --max-polls=10 || exit 1

skip 9 'anon auth not supported'  # TODO
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit

# Disable the suite passphrase (to leave us with public access privilege).
mv "${SRV_D}/passphrase" "${SRV_D}/passphrase.DIS"

# Check scan --full output.
cylc scan --comms-timeout=5 -f --color=never -n "${SUITE_NAME}" \
    >'scan-f.out' 2>'/dev/null'
cmp_ok scan-f.out << __END__
${SUITE_NAME} ${USER}@localhost:${PORT}
   (description and state totals withheld)
__END__

# Check scan --describe output.
cylc scan --comms-timeout=5 -d --color=never -n "${SUITE_NAME}" \
    >'scan-d.out' 2>'/dev/null'
cmp_ok scan-d.out << __END__
${SUITE_NAME} ${USER}@localhost:${PORT}
   (description and state totals withheld)
__END__

# Check scan --raw output.
cylc scan --comms-timeout=5 -t raw --color=never -n "${SUITE_NAME}" \
    >'scan-r.out' 2>'/dev/null'
cmp_ok scan-r.out << __END__
${SUITE_NAME}|${USER}|localhost|port|${PORT}
__END__

# Check scan --json output.
cylc scan --comms-timeout=5 -t json --color=never -n "${SUITE_NAME}" \
    >'scan-j.out' 2>'/dev/null'
cmp_json 'scan-j.out' 'scan-j.out' << __END__
[
    [
        "localhost",
        ${PORT},
        {
            "owner":"${USER}",
            "version": "$(cylc version)",
            "name":"${SUITE_NAME}"
        }
    ]
]
__END__

# "cylc show" should be denied.
TEST_NAME="${TEST_NAME_BASE}-show"
run_fail "${TEST_NAME}" cylc show "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log1
grep_ok "\[client-connect\] DENIED (privilege 'identity' < 'description') ${USER}@.*:cylc-show" suite.log1

# Commands should be denied.
TEST_NAME="${TEST_NAME_BASE}-stop"
run_fail "${TEST_NAME}" cylc stop "${SUITE_NAME}"
cylc log "${SUITE_NAME}" > suite.log2
grep_ok "\[client-connect\] DENIED (privilege 'identity' < 'shutdown') ${USER}@.*:cylc-stop" suite.log2

# Restore the passphrase.
mv "${SRV_D}/passphrase.DIS" "${SRV_D}/passphrase"

# Stop and purge the suite.
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
