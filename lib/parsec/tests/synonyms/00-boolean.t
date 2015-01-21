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
# Test parsing of boolean items
. $(dirname $0)/test_header

#-------------------------------------------------------------------------------
set_test_number 2

install_test $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-False
run_ok $TEST_NAME synonyms.py boolean

TEST_NAME=${TEST_NAME_BASE}-True
run_ok $TEST_NAME synonyms.py boolean
