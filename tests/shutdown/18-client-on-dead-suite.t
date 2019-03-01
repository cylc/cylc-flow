#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test suite shuts down with error on missing port file
. "$(dirname "$0")/test_header"
set_test_number 5
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
    [[dependencies]]
        graph = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
cylc run --hold --no-detach "${SUITE_NAME}" 1>'cylc-run.out' 2>&1 &
MYPID=$!
RUND="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
poll '!' test -f "${RUND}/.service/contact"
kill "${MYPID}"  # Should leave behind the contact file
wait "${MYPID}" 1>'/dev/null' 2>&1 || true
MYHTTP=$(sed -n 's/^CYLC_COMMS_PROTOCOL=\(.\+\)$/\1/p' "${RUND}/.service/contact")
MYHOST=$(sed -n 's/^CYLC_SUITE_HOST=\(.\+\)$/\1/p' "${RUND}/.service/contact")
MYPORT=$(sed -n 's/^CYLC_SUITE_PORT=\(.\+\)$/\1/p' "${RUND}/.service/contact")
run_fail "${TEST_NAME_BASE}-1" cylc ping "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-1.stderr" <<__ERR__
Request returned error: Suite "$SUITE_NAME" already stopped
__ERR__
run_fail "${TEST_NAME_BASE}-2" cylc ping "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-2.stderr" <<__ERR__
Contact info not found for suite "${SUITE_NAME}", suite not running?
__ERR__
purge_suite "${SUITE_NAME}"
exit
