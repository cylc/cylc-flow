#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

# Test that timed out event handlers get killed and recorded as failed.

. "$(dirname "$0")/test_header"

set_test_number 4

create_test_global_config "" "
[scheduler]
    process pool timeout = PT10S
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

sed -e 's/^.* \([EW]\)/\1/' "${WORKFLOW_RUN_DIR}/log/scheduler/log" >'log'

contains_ok 'log' <<__END__
ERROR - [(('event-handler-00', 'started'), 1) cmd] sleeper.sh 1/foo
${LOG_INDENT}[(('event-handler-00', 'started'), 1) ret_code] -9
${LOG_INDENT}[(('event-handler-00', 'started'), 1) err] killed on timeout (PT10S)
WARNING - 1/foo/01 handler:event-handler-00 for task event:started failed
__END__

cylc workflow-state --old-format "${WORKFLOW_NAME}" >'workflow-state.log'

contains_ok 'workflow-state.log' << __END__
stopper, 1, succeeded
foo, 1, succeeded
__END__

purge
exit
