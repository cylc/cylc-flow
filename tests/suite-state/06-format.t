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
#-------------------------------------------------------------------------------
# Test cylc suite-state "template" option
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" format
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-cli-template-poll
run_ok "${TEST_NAME}" cylc suite-state "${SUITE_NAME}" -p 20100101T0000Z \
        --task=foo --status=succeeded
contains_ok "${TEST_NAME}.stdout" <<__OUT__
polling for 'succeeded': satisfied
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-cli-template-dump
run_ok "${TEST_NAME}" cylc suite-state "${SUITE_NAME}" -p 20100101T0000Z
contains_ok "${TEST_NAME}.stdout" <<__OUT__
foo, 2010-01-01, succeeded
__OUT__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
#-------------------------------------------------------------------------------
exit 0
