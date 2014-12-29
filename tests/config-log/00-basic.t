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
# Test suite config logging.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run $SUITE_NAME
#-------------------------------------------------------------------------------
# Wait till the suite is finished
TEST_NAME=$TEST_NAME_BASE-monitor
RUN_DIR=$(cylc get-global-config --print-run-dir)/$SUITE_NAME
run_ok $TEST_NAME timeout 30 \
  $(cylc get-directory $SUITE_NAME)/bin/file-watcher.sh $RUN_DIR/suite-stopping
#-------------------------------------------------------------------------------
# Check for three dumped configs.
TEST_NAME=$TEST_NAME_BASE-logs
LOG_DIR=${RUN_DIR}/log/suiterc
ls $LOG_DIR | sed -e 's/.*-//g' > logs.txt
cmp_ok logs.txt <<__END__
run.rc
reload.rc
restart.rc
__END__
#-------------------------------------------------------------------------------
# The run and reload logs should be identical.
TEST_NAME=$TEST_NAME_BASE-comp1
RUN_LOG=$(ls $LOG_DIR/*run.rc)
REL_LOG=$(ls $LOG_DIR/*reload.rc)
RES_LOG=$(ls $LOG_DIR/*restart.rc)
cmp_ok $RUN_LOG $REL_LOG
#-------------------------------------------------------------------------------
# The run and restart logs should differ in the suite description.
TEST_NAME=$TEST_NAME_BASE-comp1
sort $RUN_LOG $RES_LOG | uniq -u > diff.txt
cmp_ok diff.txt <<__END__
description = the weather is bad
description = the weather is good
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
