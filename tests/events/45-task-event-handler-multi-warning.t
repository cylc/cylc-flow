#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
# Test that simultaneous warnings from a task job are all handled by the
# warning event handler.
# https://github.com/cylc/cylc/issues/2806

. "$(dirname "$0")/test_header"

set_test_number 3

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
   [[dependencies]]
      graph = foo
[runtime]
   [[foo]]
      script = """
cylc message -s WARNING -- ${CYLC_SUITE_NAME} ${CYLC_TASK_JOB} "cat"
cylc message -s WARNING -- ${CYLC_SUITE_NAME} ${CYLC_TASK_JOB} "dog"
cylc message -s WARNING -- ${CYLC_SUITE_NAME} ${CYLC_TASK_JOB} "fish"
cylc message -s WARNING -- ${CYLC_SUITE_NAME} ${CYLC_TASK_JOB} "guinea pig"
"""
      [[[events]]]
        handler events = warning
        handlers = echo "HANDLED %(message)s"
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"

cylc cat-log "${SUITE_NAME}" \
    | sed -n -e 's/^.*\(\[(('"'"'event-handler-00'"'"'.*$\)/\1/p' >'log'

cmp_ok log <<__END__
[(('event-handler-00', 'warning-cat'), 1) cmd] echo "HANDLED cat"
[(('event-handler-00', 'warning-cat'), 1) ret_code] 0
[(('event-handler-00', 'warning-cat'), 1) out] HANDLED cat
[(('event-handler-00', 'warning-dog'), 1) cmd] echo "HANDLED dog"
[(('event-handler-00', 'warning-dog'), 1) ret_code] 0
[(('event-handler-00', 'warning-dog'), 1) out] HANDLED dog
[(('event-handler-00', 'warning-fish'), 1) cmd] echo "HANDLED fish"
[(('event-handler-00', 'warning-fish'), 1) ret_code] 0
[(('event-handler-00', 'warning-fish'), 1) out] HANDLED fish
[(('event-handler-00', 'warning-guinea%20pig'), 1) cmd] echo "HANDLED 'guinea pig'"
[(('event-handler-00', 'warning-guinea%20pig'), 1) ret_code] 0
[(('event-handler-00', 'warning-guinea%20pig'), 1) out] HANDLED 'guinea pig'
__END__

purge_suite "${SUITE_NAME}"
exit
