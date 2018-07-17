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

# Test cylc-doc on suite and task URLs: old back-compat form with pseudo
# environment vars rather than string templating. (c.f. 02-suite-urls.t).

. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
create_test_globalrc "" "
[documentation]
   [[files]]
      pdf user guide = ${PWD}/doc/pdf/cug-pdf.pdf
      multi-page html user guide = /home/bob/cylc/cylc.git/doc/html/multi/cug-html.html
      html index = /home/bob/cylc/cylc.git/doc/index.html
      single-page html user guide = /home/bob/cylc/cylc.git/doc/html/single/cug-html.html
   [[urls]]
      internet homepage = http://cylc.github.com/cylc/
      local index = http://localhost/cylc/index.html"
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-validate
run_ok $TEST_NAME cylc validate "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-url
cylc doc -s $SUITE_NAME > stdout1.txt
cmp_ok stdout1.txt <<__END__
http://localhost/suite-docs/${SUITE_NAME}.html
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-url
cylc doc -s -t bar $SUITE_NAME > stdout2.txt
cmp_ok stdout2.txt <<__END__
http://localhost/suite-docs/${SUITE_NAME}.html#bar
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
#-------------------------------------------------------------------------------
