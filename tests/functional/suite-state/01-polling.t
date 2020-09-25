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
#-------------------------------------------------------------------------------
# Validate and run the suite-state/polling test suite
# The test suite is in polling/; it depends on another suite in upstream/

. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" 'polling'
#-------------------------------------------------------------------------------
# copy the upstream suite to the test directory and register it
cp -r "${TEST_SOURCE_DIR}/upstream" "${TEST_DIR}/"
# this version uses a simple Rose-style suite name [\w-]
UPSTREAM="${SUITE_NAME}-upstream"
cylc reg "${UPSTREAM}" "${TEST_DIR}/upstream"
#-------------------------------------------------------------------------------
# validate both suites as tests
TEST_NAME="${TEST_NAME_BASE}-validate-upstream"
run_ok "${TEST_NAME}" cylc val --debug "${UPSTREAM}"

TEST_NAME="${TEST_NAME_BASE}-validate-polling"
run_ok "${TEST_NAME}" \
    cylc val --debug --set="UPSTREAM=${UPSTREAM}" "${SUITE_NAME}"

#-------------------------------------------------------------------------------
# check auto-generated task script for lbad
cylc get-config \
    --set="UPSTREAM=${UPSTREAM}" \
    -i '[runtime][lbad]script' "${SUITE_NAME}" >'lbad.script'
cmp_ok 'lbad.script' << __END__
echo cylc suite-state --task=bad --point=\$CYLC_TASK_CYCLE_POINT --interval=2 --max-polls=20 --status=fail ${UPSTREAM}
cylc suite-state --task=bad --point=\$CYLC_TASK_CYCLE_POINT --interval=2 --max-polls=20 --status=fail ${UPSTREAM}
__END__

# check auto-generated task script for l-good
cylc get-config \
    --set="UPSTREAM=${UPSTREAM}" \
    -i '[runtime][l-good]script' "${SUITE_NAME}" >'l-good.script'
cmp_ok 'l-good.script' << __END__
echo cylc suite-state --task=good-stuff --point=\$CYLC_TASK_CYCLE_POINT --interval=2 --max-polls=20 --status=succeed ${UPSTREAM}
cylc suite-state --task=good-stuff --point=\$CYLC_TASK_CYCLE_POINT --interval=2 --max-polls=20 --status=succeed ${UPSTREAM}
__END__

#-------------------------------------------------------------------------------
# run the upstream suite and detach (not a test)
cylc run "${UPSTREAM}" 1>'upstream.out' 2>&1

#-------------------------------------------------------------------------------
# run the suite-state polling test suite
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" \
    cylc run --reference-test --debug --no-detach --set="UPSTREAM=${UPSTREAM}" \
    "${SUITE_NAME}"

#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"

#-------------------------------------------------------------------------------
# clean up the upstream suite
# just in case (expect error message here, but exit 0):
cylc stop --now "${UPSTREAM}" --max-polls=20 --interval=2 >'/dev/null' 2>&1
purge_suite "${UPSTREAM}"
exit
