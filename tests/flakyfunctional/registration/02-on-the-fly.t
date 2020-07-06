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
# Test on-the-fly suite registration by "cylc run"
#------------------------------------------------------------------------------
# Test `cylc run` with no registration

. "$(dirname "$0")/test_header"
set_test_number 9

TEST_NAME="${TEST_NAME_BASE}-pwd"

TESTD="cylctb-cheese-${CYLC_TEST_TIME_INIT}"
mkdir "${TESTD}"
cat >> "${TESTD}/suite.rc" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

cd "${TESTD}" || exit 1
run_ok "${TEST_NAME}-run" cylc run --hold
contains_ok "${TEST_NAME}-run.stdout" <<__ERR__
REGISTERED ${TESTD} -> ${PWD}
__ERR__

run_ok "${TEST_NAME}-stop" cylc stop --max-polls=10 --interval=2 "${TESTD}"

purge_suite "${TESTD}"
#------------------------------------------------------------------------------
# Test `cylc run` REG for an un-registered suite
TESTD="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_NAME_BASE}"

mkdir -p "${RUN_DIR}/${TESTD}"
cat >> "${RUN_DIR}/${TESTD}/suite.rc" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

TEST_NAME="${TEST_NAME_BASE}-cylc-run-dir"
run_ok "${TEST_NAME}-run" cylc run --hold "${TESTD}"
contains_ok "${TEST_NAME}-run.stdout" <<__ERR__
REGISTERED ${TESTD} -> ${RUN_DIR}/${TESTD}
__ERR__

run_ok "${TEST_NAME}-stop" cylc stop  --max-polls=10 --interval=2 "${TESTD}"

purge_suite "${TESTD}"
#------------------------------------------------------------------------------
# Test `cylc run` REG for an un-registered suite
mkdir -p "${RUN_DIR}/${TESTD}"
cat >> "${RUN_DIR}/${TESTD}/suite.rc" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[sched]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
__SUITE_RC__

TEST_NAME="${TEST_NAME_BASE}-cylc-run-dir-2"
run_fail "${TEST_NAME}-validate" cylc validate "${TESTD}"
contains_ok "${TEST_NAME}-validate.stdout" <<__OUT__
REGISTERED ${TESTD} -> ${RUN_DIR}/${TESTD}
__OUT__
contains_ok "${TEST_NAME}-validate.stderr" <<__ERR__
IllegalItemError: sched
__ERR__

purge_suite "${TESTD}"

exit
