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
#------------------------------------------------------------------------------

# Test suite-state xtriggers with suite depends on an upstream suite
# that stops once cycle short, so it should abort with waiting tasks.

. "$(dirname "$0")/test_header"
set_test_number 8

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Register and validate the upstream suite.
SUITE_NAME_UPSTREAM="${SUITE_NAME}-upstream"
cylc reg "${SUITE_NAME_UPSTREAM}" "${TEST_DIR}/${SUITE_NAME}/upstream"
run_ok "${TEST_NAME_BASE}-val-up" cylc val --debug "${SUITE_NAME_UPSTREAM}"

# Validate the downstream test suite.
run_ok "${TEST_NAME_BASE}-val" \
    cylc val --debug --set="UPSTREAM=${SUITE_NAME_UPSTREAM}" "${SUITE_NAME}"

# Run the upstream suite and detach (not a test).
cylc run "${SUITE_NAME_UPSTREAM}"

# Run the test suite - it should fail after inactivity ...
TEST_NAME="${TEST_NAME_BASE}-run-fail"
suite_run_fail "${TEST_NAME}" \
   cylc run --set="UPSTREAM=${SUITE_NAME_UPSTREAM}" --no-detach "${SUITE_NAME}"

SUITE_LOG="$(cylc cat-log -m 'p' "${SUITE_NAME}")"
grep_ok 'WARNING - suite timed out after inactivity for PT10S' "${SUITE_LOG}"

# ... with foo.2016 succeeded and FAM.2016 waiting.
cylc suite-state -p '2016' "${SUITE_NAME}" >'suite_state.out'
contains_ok 'suite_state.out' << __END__
foo, 2016, succeeded
f3, 2016, waiting
f1, 2016, waiting
f2, 2016, waiting
__END__

# Check broadcast of xtrigger outputs to dependent tasks.
JOB_LOG="$(cylc cat-log -f 'j' -m 'p' "${SUITE_NAME}" 'f1.2015')"
contains_ok "${JOB_LOG}" << __END__
    upstream_task="foo"
    upstream_point="2015"
    upstream_status="succeeded"
    upstream_message="data ready"
    upstream_offset="None"
    upstream_suite="${SUITE_NAME_UPSTREAM}"
__END__

# Check broadcast of xtrigger outputs is recorded: 1) in the suite log...
#
# Lines are those which should appear after a '<datetimestamp> INFO - Broadcast
# set' ('+') and later '... INFO - Broadcast cancelled:' ('-') line, where we
# use as a test case an arbitary task where such setting & cancellation occurs:
contains_ok "${SUITE_LOG}" << __LOG_BROADCASTS__
	+ [f1.2015] [environment]upstream_suite=${SUITE_NAME_UPSTREAM}
	+ [f1.2015] [environment]upstream_task=foo
	+ [f1.2015] [environment]upstream_point=2015
	+ [f1.2015] [environment]upstream_offset=None
	+ [f1.2015] [environment]upstream_status=succeeded
	+ [f1.2015] [environment]upstream_message=data ready
	- [f1.2015] [environment]upstream_suite=${SUITE_NAME_UPSTREAM}
	- [f1.2015] [environment]upstream_task=foo
	- [f1.2015] [environment]upstream_point=2015
	- [f1.2015] [environment]upstream_status=succeeded
	- [f1.2015] [environment]upstream_message=data ready
__LOG_BROADCASTS__
# ... and 2) in the DB.
TEST_NAME="${TEST_NAME_BASE}-check-broadcast-in-db"
if ! command -v 'sqlite3' >'/dev/null'; then
    skip 1 "sqlite3 not installed?"
fi
DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/log/db"
NAME='db-broadcast-states.out'
sqlite3 "${DB_FILE}" \
    'SELECT change, point, namespace, key, value FROM broadcast_events
     ORDER BY time, change, point, namespace, key' >"${NAME}"
contains_ok "${NAME}" << __DB_BROADCASTS__
+|2015|f1|[environment]upstream_message|data ready
+|2015|f1|[environment]upstream_offset|None
+|2015|f1|[environment]upstream_point|2015
+|2015|f1|[environment]upstream_status|succeeded
+|2015|f1|[environment]upstream_suite|${SUITE_NAME_UPSTREAM}
+|2015|f1|[environment]upstream_task|foo
-|2015|f1|[environment]upstream_message|data ready
-|2015|f1|[environment]upstream_point|2015
-|2015|f1|[environment]upstream_status|succeeded
-|2015|f1|[environment]upstream_suite|${SUITE_NAME_UPSTREAM}
-|2015|f1|[environment]upstream_task|foo
__DB_BROADCASTS__

purge_suite "${SUITE_NAME}"

# Clean up the upstream suite, just in case (expect error here, but exit 0):
cylc stop --now "${SUITE_NAME_UPSTREAM}" --max-polls=20 --interval=2 \
    >'/dev/null' 2>&1
purge_suite "${SUITE_NAME_UPSTREAM}"
exit
