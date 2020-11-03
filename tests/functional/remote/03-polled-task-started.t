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
# -----------------------------------------------------------------------------
# Test that a quickly finishing task's `:start` trigger does not get missed
# when using polling to get remote task status.

. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 4

create_test_global_config '' "
[platforms]
    [[enterprise]]
        hosts = $CYLC_TEST_HOST
        communication method = poll
        submission polling intervals = PT5S
        execution polling intervals = PT5S
"
install_suite

run_ok "${TEST_NAME_BASE}-validate" cylc validate "$SUITE_NAME"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --reference-test --no-detach "$SUITE_NAME"

PICARD_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/picard/01/job-activity.log"
grep_ok "[(('event-handler-00', 'started'), 1) out] THERE ARE FOUR LIGHTS" "$PICARD_ACTIVITY_LOG" -F

JANEWAY_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/janeway/01/job-activity.log"
grep_ok "[(('event-handler-00', 'started'), 1) out] THERE'S COFFEE IN THAT NEBULA" "$JANEWAY_ACTIVITY_LOG" -F

purge_suite "$SUITE_NAME"
purge_suite_platform "$CYLC_TEST_PLATFORM" "$SUITE_NAME"
exit
