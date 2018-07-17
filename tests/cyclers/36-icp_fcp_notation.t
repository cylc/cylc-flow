#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & contributors
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
# Test intercycle dependencies.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
# test initial and final cycle point special notation (^, $)
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

grep_ok '\[foo\.20160101T0000Z\]' "${SUITE_RUN_DIR}/log/suite/log"
grep_ok '\[bar\.20160101T0000Z\]' "${SUITE_RUN_DIR}/log/suite/log"
grep_ok '\[baz\.20160101T0100Z\]' "${SUITE_RUN_DIR}/log/suite/log"
grep_ok '\[boo\.20160101T2300Z\]' "${SUITE_RUN_DIR}/log/suite/log"
grep_ok '\[bot\.20160102T0000Z\]' "${SUITE_RUN_DIR}/log/suite/log"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
