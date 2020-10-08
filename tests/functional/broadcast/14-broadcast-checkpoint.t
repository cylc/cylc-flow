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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test broadcast checkpoint values persisted in the database
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-run-suite
run_ok "${TEST_NAME}" cylc run --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# The first broadcast checkpoint must contain only
# one broadcast state - the first we submitted.
cylc ls-checkpoint "${SUITE_NAME}" 1 > ls-check-point-output.log
grep_ok "VERSE" ls-check-point-output.log
grep_fail "PHRASE" ls-check-point-output.log
#-------------------------------------------------------------------------------
# Whereas the second broadcast checkpoint must contain
# two broadcast states - the first we submitted, and the
# subsequent one as well.
cylc ls-checkpoint "${SUITE_NAME}" 2 > ls-check-point-output.log
grep_ok "VERSE" ls-check-point-output.log
grep_ok "PHRASE" ls-check-point-output.log
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
