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
# Test `cylc scan` output.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = sleep 60
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"


SRV_D="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/.service"
HOST="$(sed -n 's/^CYLC_SUITE_HOST=//p' "${SRV_D}/contact")"
PORT="$(sed -n 's/^CYLC_SUITE_PORT=//p' "${SRV_D}/contact")"
PUBLISH_PORT="$(sed -n 's/^CYLC_SUITE_PUBLISH_PORT=//p' "${SRV_D}/contact")"

# test normal scan
TEST_NAME="${TEST_NAME_BASE}-scan-1"
run_ok "${TEST_NAME}" cylc scan --color=never -n "${SUITE_NAME}"
cmp_ok "${TEST_NAME}.stdout" <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT}
__END__

# test publisher
TEST_NAME="${TEST_NAME_BASE}-scan-2"
run_ok "${TEST_NAME}" cylc scan --comms-timeout=10 --publisher --color=never -n "${SUITE_NAME}"
cmp_ok "${TEST_NAME}.stdout" <<__END__
${SUITE_NAME} ${USER}@${HOST}:${PORT} ${USER}@${HOST}:${PUBLISH_PORT}
__END__

# test full
TEST_NAME="${TEST_NAME_BASE}-scan-3"
run_ok "${TEST_NAME}" cylc scan --color=never --full -n "${SUITE_NAME}"
grep_ok "${SUITE_NAME}" "${TEST_NAME}.stdout"

cylc stop --kill --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
