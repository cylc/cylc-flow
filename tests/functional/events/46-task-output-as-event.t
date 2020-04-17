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
# Test that known task outputs can be used as events.

. "$(dirname "$0")/test_header"

set_test_number 3

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
   [[graph]]
      R1 = t1
[runtime]
    [[t1]]
        script="""
cylc message -- ${CYLC_SUITE_NAME} ${CYLC_TASK_JOB} \
    'rose' 'lily' 'iris' 'WARNING:poison ivy'
"""
        [[[outputs]]]
            rose = rose
            lily = lily
            iris = iris
        [[[events]]]
            handler events = rose, lily, iris, warning
            handlers = echo %(message)s
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
cylc cat-log "${SUITE_NAME}" \
    | sed -n -e 's/^.*\(\[(('"'"'event-handler-00'"'"'.*$\)/\1/p' | sort >'log'

cmp_ok log <<__END__
[(('event-handler-00', 'iris'), 1) cmd] echo iris
[(('event-handler-00', 'iris'), 1) out] iris
[(('event-handler-00', 'iris'), 1) ret_code] 0
[(('event-handler-00', 'lily'), 1) cmd] echo lily
[(('event-handler-00', 'lily'), 1) out] lily
[(('event-handler-00', 'lily'), 1) ret_code] 0
[(('event-handler-00', 'rose'), 1) cmd] echo rose
[(('event-handler-00', 'rose'), 1) out] rose
[(('event-handler-00', 'rose'), 1) ret_code] 0
[(('event-handler-00', 'warning-1'), 1) cmd] echo 'poison ivy'
[(('event-handler-00', 'warning-1'), 1) out] poison ivy
[(('event-handler-00', 'warning-1'), 1) ret_code] 0
__END__

purge_suite "${SUITE_NAME}"
exit
