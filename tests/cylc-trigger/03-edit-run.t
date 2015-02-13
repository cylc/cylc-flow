#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test an edit-run (cylc trigger --edit).
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Configure a fake editor $PWD/bin/my-edit via $PWD/conf and run a suite
# containing a task that does an edit run.
TEST_NAME="${TEST_NAME_BASE}-run"
CYLC_CONF_PATH=$PWD/conf \
    run_ok "${TEST_NAME}" cylc run --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
