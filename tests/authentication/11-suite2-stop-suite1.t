#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test calling "cylc shutdown suite1" from suite2.
# See https://github.com/cylc/cylc/issues/1843
. "$(dirname "$0")/test_header"

set_test_number 1

RUND="$(cylc get-global-config --print-run-dir)"
SUITE1_RUND="$(mktemp -d --tmpdir="${RUND}" 'ctb-authentication-11-XXXXXXXX')"
SUITE1="$(basename "${SUITE1_RUND}")"
SUITE2_RUND="$(mktemp -d --tmpdir="${RUND}" 'ctb-authentication-11-XXXXXXXX')"
SUITE2="$(basename "${SUITE2_RUND}")"
cp -p "${TEST_SOURCE_DIR}/basic/suite.rc" "${SUITE1_RUND}"
cylc register "${SUITE1}" "${SUITE1_RUND}"
cat >"${SUITE2_RUND}/suite.rc" <<__SUITERC__
[cylc]
    abort if any task fails=True
[scheduling]
    [[dependencies]]
        graph=t1
[runtime]
    [[t1]]
        script=cylc shutdown "${SUITE1}"
__SUITERC__
cylc register "${SUITE2}" "${SUITE2_RUND}"
cylc run --no-detach "${SUITE1}" 1>'1.out' 2>&1 &
poll '!' test -e "${SUITE1_RUND}/.cylc-var/contact"
run_ok "${TEST_NAME_BASE}" cylc run --no-detach "${SUITE2}"
cylc shutdown "${SUITE1}" --max-polls=10 --interval=1 1>'/dev/null' 2>&1 || true
purge_suite "${SUITE1}"
purge_suite "${SUITE2}"
rm -fr "${SUITE1_RUND}" "${SUITE2_RUND}"
exit
