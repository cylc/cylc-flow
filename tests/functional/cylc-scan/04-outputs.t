#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2020 NIWA & British Crown (Met Office) & Contributors.
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

# Test Cylc Scan output

. "$(dirname "$0")/test_header"
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

# Run the suite.
cylc run "${SUITE_NAME}"

# Wait for first task 'foo' to fail.
cylc suite-state "${SUITE_NAME}" --task=foo --status=failed --point=1 \
    --interval=1 --max-polls=20 || exit 1
# Check scan --full output.
SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"
PUBLISH_PORT="$(sed -n 's/^CYLC_SUITE_PUBLISH_PORT=//p' "${SRV_D}/contact")"
CYLC_VERSION="$(sed -n 's/^CYLC_VERSION=//p' "${SRV_D}/contact")"

cylc scan --comms-timeout=5 -f --color=never -n "${SUITE_NAME}" \
    >'scan-f.out' # 2>'/dev/null'
cmp_ok 'scan-f.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT} ${USER}@${HOST}:${PUBLISH_PORT}
   Title:
      Cylc Scan test suite.
   Description:
      Stalls when the first task fails.
      Here we test out a multi-line description!
   Group:
      (no Group)
   API:
      5
   URL:
      (no URL)
   another_metadata:
      1
   custom_metadata:
      something_custom
   Task state totals:
      failed:1 waiting:1
      1 failed:1 waiting:1
__END__

# Check scan --describe output.
cylc scan --comms-timeout=5 -d --color=never -n "${SUITE_NAME}" \
    >'scan-d.out' # 2>'/dev/null'
cmp_ok 'scan-d.out' <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT}
   Title:
      Cylc Scan test suite.
   Description:
      Stalls when the first task fails.
      Here we test out a multi-line description!
   Group:
      (no Group)
   API:
      5
   URL:
      (no URL)
   another_metadata:
      1
   custom_metadata:
      something_custom
__END__

# Check scan --raw output.
cylc scan --comms-timeout=5 -t raw --color=never -n "${SUITE_NAME}" \
    >'scan-r.out' # 2>'/dev/null'
cmp_ok 'scan-r.out' <<__END__
${SUITE_NAME}|${USER}|${HOST}|port|${PORT}
__END__

# Check scan --json output.
cylc scan --comms-timeout=5 -t json --color=never -n "${SUITE_NAME}" \
    >'scan-j.out' # 2>'/dev/null'
cmp_json 'scan-j.out' 'scan-j.out' <<__END__
[
    [   "${SUITE_NAME}",
        "${HOST}",
        "${PORT}",
        "$PUBLISH_PORT",
        "5",
        {"name":"${SUITE_NAME}", "owner": "${USER}", "version": "${CYLC_VERSION}"}

    ]
]
__END__

# Stop and purge the suite.
cylc stop --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
