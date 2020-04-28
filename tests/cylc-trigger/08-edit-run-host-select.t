#!/bin/bash
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
# Test an edit-run (cylc trigger --edit) with host-select command.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
# Configure a fake editor and run a suite with a task that does an edit run.
create_test_globalrc '' '
[editors]
    terminal = my-edit'
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" cylc run --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-diff"
DIFF_LOG="$(cylc cat-log -m p -f d "${SUITE_NAME}" 'broken-task.1')"
# Python 2.6 difflib adds an extra space after the filename,
# but Python 2.7 does not. Remove it if it exists.
sed -i 's/^\(--- original\|+++ edited\) $/\1/; /^@@/d' "${DIFF_LOG}"
cmp_ok "${DIFF_LOG}" - <<__END__
--- original
+++ edited
 
 cylc__job__inst__script() {
 # SCRIPT:
-false
+true
 }
 
 . "${SUITE_RUN_DIR}/.service/etc/job.sh"
__END__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
