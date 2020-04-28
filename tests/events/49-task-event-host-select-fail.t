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

# Ensure that submission failed handler on task host-select failure runs OK.

. "$(dirname "$0")/test_header"
set_test_number 3
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on stalled = True
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = true
        [[[events]]]
            submission failed handler = echo empty [%(user@host)s]?
        [[[remote]]]
            host = $(false)
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_fail "${TEST_NAME_BASE}-run" cylc run --no-detach "${SUITE_NAME}"

run_ok "log-handler-out" \
    grep -qF '[(('"'"'event-handler-00'"'"', '"'"'submission failed'"'"'), 1) out] empty []?' \
    "${SUITE_RUN_DIR}/log/suite/log"

purge_suite "${SUITE_NAME}"
exit
