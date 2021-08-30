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
# Test that abort on stall does not apply to a paused workflow

# See also tests/functional/events/25-held-not-stalled.t

. "$(dirname "$0")/test_header"
set_test_number 2


init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduler]
    [[events]]
        abort on inactivity = False
        abort on stall = True
        inactivity handler = cylc play '%(workflow)s'
        inactivity = PT5S
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --pause --no-detach "${WORKFLOW_NAME}"

purge
