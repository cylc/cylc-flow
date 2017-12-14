#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test cylc scan is picking up running suite
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 6
create_test_globalrc
host_port_ref () {
  SUITE=$1
  FQDN=$(python -c "import sys
sys.path.insert(0, '$CYLC_HOME')
import cylc.hostuserutil
print cylc.hostuserutil.get_fqdn_by_host('`hostname`')")
  PORT=$(sed -n 's/CYLC_SUITE_PORT=//p' \
    "${HOME}/cylc-run/${SUITE}/.service/contact")
  echo "$SUITE `whoami`@$FQDN:$PORT"
}
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE ctb-cylc-scan-simple
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
run_ok $TEST_NAME cylc run $SUITE_NAME --hold
SCAN_LINE=$(host_port_ref "${SUITE_NAME}")
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-basic
run_ok $TEST_NAME cylc scan --no-bold -n "$SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" <<<${SCAN_LINE}
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-describe
run_ok $TEST_NAME cylc scan --no-bold --describe -n "$SUITE_NAME"
cmp_ok "$TEST_NAME.stdout" <<__SHOW_OUTPUT__
${SCAN_LINE}
   Title:
      "A simple test"
   Group:
      (no group)
   Description:
      "A simple test to simply test whether cylc scan is
       doing the right thing - let's see what happens."
   URL:
      (no URL)
   datum:
      "metadatum"
   another_datum:
      "another_metadatum"
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
cylc stop $SUITE_NAME --now
purge_suite $SUITE_NAME
