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
# Test that members of namespace lists [[n1,n2,...]] are inserted into the
# [runtime] ordered dict in the correct order. If just appended, they break
# repeat-section override for the member.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-config
cylc config -i runtime "${WORKFLOW_NAME}" > runtime.out
cmp_ok runtime.out <<'__DONE__'
[[root]]
[[FAMILY]]
[[m1]]
    inherit = FAMILY
    completion = succeeded
    [[[environment]]]
        FOO = foo
[[m2]]
    inherit = FAMILY
    completion = succeeded
    [[[environment]]]
        FOO = bar
[[m3]]
    inherit = FAMILY
    completion = succeeded
    [[[environment]]]
        FOO = foo
__DONE__
#-------------------------------------------------------------------------------
purge
exit
