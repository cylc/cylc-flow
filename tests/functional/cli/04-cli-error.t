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

# Get coverage up for some CLI parser errors. 

. "$(dirname "$0")/test_header"
set_test_number 4

init_workflow "${TEST_NAME_BASE}" << __CONFIG__
[scheduling]
   [[graph]]
       R1 = foo
[runtime]
   [[foo]]
__CONFIG__

# "cylc set-outputs" requires a flow number.
TEST_NAME="set-outputs-fail"
run_fail "${TEST_NAME}"  \
    cylc set-outputs "${WORKFLOW_NAME}"  foo.1
contains_ok "${TEST_NAME}".stderr <<__END__
cylc: error: --flow=FLOW is required.
__END__

# "cylc trigger --meta" requires --reflow
TEST_NAME="set-trigger-fail"
run_fail "${TEST_NAME}"  \
    cylc trigger --meta="the quick brown" "${WORKFLOW_NAME}"  foo.1
contains_ok "${TEST_NAME}".stderr <<__END__
cylc: error: --meta requires --reflow
__END__

purge
