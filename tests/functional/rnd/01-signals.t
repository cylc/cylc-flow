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
# Test scheduler signal handling
# # See https://github.com/cylc/cylc-flow/issues/6438

. "$(dirname "$0")/test_header"
set_test_number 6


init_workflow "${TEST_NAME_BASE}" <<__FLOW__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
__FLOW__


# test signals on a detached scheduler
TEST_NAME="${TEST_NAME_BASE}-detatch"
cylc play "${WORKFLOW_NAME}" --pause
poll_workflow_running
PID="$(sed -n 's/CYLC_WORKFLOW_PID=//p' "$HOME/cylc-run/$WORKFLOW_NAME/.service/contact")"
kill -s SIGINT "$PID"
poll_workflow_stopped
log_scan "${TEST_NAME}" "$(cylc cat-log -m p "${WORKFLOW_NAME}")" 10 1 \
    'Signal SIGINT received' \
    'Workflow shutting down - REQUEST(NOW)' \
    'DONE'


# test signals on a non-detached scheduler
TEST_NAME="${TEST_NAME_BASE}-no-detach"
cylc play "${WORKFLOW_NAME}" --pause --no-detach 2>/dev/null &
poll_workflow_running
PID="$(sed -n 's/CYLC_WORKFLOW_PID=//p' "$HOME/cylc-run/$WORKFLOW_NAME/.service/contact")"
kill -s SIGTERM "$PID"
poll_workflow_stopped
log_scan "${TEST_NAME}" "$(cylc cat-log -m p "${WORKFLOW_NAME}")" 10 1 \
    'Signal SIGTERM received' \
    'Workflow shutting down - REQUEST(NOW)' \
    'DONE'


purge
