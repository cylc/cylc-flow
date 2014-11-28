#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test validation missing include-file.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
echo '%include foo.rc' >suite.rc
echo '%include bar.rc' >foo.rc
run_fail "$TEST_NAME_BASE" cylc validate suite.rc
cmp_ok "$TEST_NAME_BASE.stderr" <<__ERR__
ParseError: File not found: $PWD/bar.rc
   via $PWD/foo.rc
   via $PWD/suite.rc
__ERR__
#-------------------------------------------------------------------------------
exit
