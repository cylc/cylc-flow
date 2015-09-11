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
# Test reset to waiting for 2 tasks with dependencies t1=>t2
# See https://github.com/cylc/cylc/pull/947
. $(dirname $0)/test_header
poll_while() {
    local TIMEOUT=$(($(date +%s) + 120)) # poll for 2 minutes
    while (($(date +%s) < $TIMEOUT)) && eval "$@" >/dev/null 2>&1; do
        sleep 1
    done
}
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "$TEST_NAME_BASE" "$TEST_NAME_BASE"
#-------------------------------------------------------------------------------
TEST_NAME="$TEST_NAME_BASE-validate"
run_ok "$TEST_NAME" cylc validate "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME="$TEST_NAME_BASE-run"
run_ok "$TEST_NAME" cylc run "$SUITE_NAME"
SUITE_RUN_DIR=$(cylc get-global-config --print-run-dir)/$SUITE_NAME
poll_while ! test -e "$SUITE_RUN_DIR/log/job/1/t1/02/job.status"
#-------------------------------------------------------------------------------
# Ensure that t2.1.2 is waiting for t1.1.2
TEST_NAME="$TEST_NAME_BASE-show-t2.1.out"
cylc show "$SUITE_NAME" t2.1 | sed -n '/^prerequisites/{N;p;}' >"$TEST_NAME"
cmp_ok "$TEST_NAME" <<__OUT__
prerequisites (- => not satisfied):
  - t1.1 succeeded
__OUT__
touch "$SUITE_RUN_DIR/t1.1.txt" # Release t1.1.2
#-------------------------------------------------------------------------------
poll_while test -e "$HOME/.cylc/ports/$SUITE_NAME"
purge_suite "$SUITE_NAME"
exit
