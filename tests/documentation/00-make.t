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
# Test documentation can be made
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
if [[ ! -w $CYLC_DIR/doc ]]; then
    skip_all '$CYLC_DIR/doc: not writable'
fi
#-------------------------------------------------------------------------------
set_test_number 1
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-make-docs
run_ok $TEST_NAME make -C $CYLC_DIR/doc
#-------------------------------------------------------------------------------
exit
