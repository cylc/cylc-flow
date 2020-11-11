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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Check that setting the platform to localhost for dummy-local mode doesn't
# cause conflicts with Cylc 7 settings
# TODO Remove test at Cylc 9.
. "$(dirname "$0")/test_header"
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Ensure that you can validate suite
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}"
         
run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --no-detach --mode=dummy-local

# Check that the upgradeable config has been run on a sensible host.
grep_ok \
    "(dummy job succeed)"\
    "${SUITE_RUN_DIR}/log/job/1/upgradeable_cylc7_settings/NN/job.out"

purge
exit
