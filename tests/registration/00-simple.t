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
# Test cylc suite registration

. "$(dirname "$0")/test_header"
set_test_number 7

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[scheduling]
    [[dependencies]]
        graph = a => b => c
[runtime]
    [[a,b,c]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-register" cylc register "${SUITE_NAME}"
exists_ok "${SUITE_RUN_DIR}/.service/passphrase"

run_ok "${TEST_NAME_BASE}-get-dir" cylc get-directory "${SUITE_NAME}"

cd .. # necessary so the suite is being validated via the database not filepath
run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}"
cd "${OLDPWD}"

run_ok "${TEST_NAME_BASE}-print" cylc print
contains_ok "${TEST_NAME_BASE}-print.stdout" <<__OUT__
${SUITE_NAME} | the quick brown fox | ${TEST_DIR}/${SUITE_NAME}
__OUT__

# Filter out errors from 'bad' suites in the 'cylc-run' directory
NONSPECIFIC_ERR2='\[Errno 2\] No such file or directory:'
SPECIFIC_ERR2="$NONSPECIFIC_ERR2 '$HOME/cylc-run/$SUITE_NAME/suite.rc'"
ERR2_COUNT=$(grep -c "$SPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr")
if [ "$ERR2_COUNT" -eq "0" ]; then
    grep -v -s "$NONSPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr" > "${TEST_NAME_BASE}-print-filtered.stderr"
    cmp_ok "${TEST_NAME_BASE}-print-filtered.stderr" <'/dev/null'
else
    fail "${TEST_NAME_BASE}-print.stderr"
fi

purge_suite "${SUITE_NAME}"
exit
