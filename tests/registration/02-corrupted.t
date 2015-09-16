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
#------------------------------------------------------------------------------
# Check a corrupted suite registration doesn't prevent access to other reg's.
. $(dirname $0)/test_header
#------------------------------------------------------------------------------
set_test_number 3
#------------------------------------------------------------------------------
mkdir $TEST_DIR/REGDB
mkdir $TEST_DIR/suite
cat > $TEST_DIR/suite/suite.rc <<__END__
[scheduling]
   [[dependencies]]
       graph = foo
__END__
# Register some suites.
cylc reg --db=$TEST_DIR/REGDB my.suite.1 $TEST_DIR/suite
cylc reg --db=$TEST_DIR/REGDB my.suite.2 $TEST_DIR/suite
cylc reg --db=$TEST_DIR/REGDB my.suite.3 $TEST_DIR/suite
# Make a corrupted registration file.
touch $TEST_DIR/REGDB/junk

#------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-print
run_ok $TEST_NAME cylc db print --db=$TEST_DIR/REGDB
cmp_ok <(sort $TEST_NAME.stdout) - << __OUT__
my.suite.1 | No title provided | $TEST_DIR/suite
my.suite.2 | No title provided | $TEST_DIR/suite
my.suite.3 | No title provided | $TEST_DIR/suite
__OUT__
grep_ok "ERROR, junk suite registration corrupted?" $TEST_NAME.stderr
