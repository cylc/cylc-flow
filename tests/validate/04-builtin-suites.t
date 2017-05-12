#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Ensure that any changes to cylc haven't broken the profile-battery command
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
# Generate a list of suites.
SUITES=($(find "${CYLC_DIR}/"{examples,dev/suites} -name 'suite.rc'))
ABS_PATH_LENGTH=${#CYLC_DIR}
#-------------------------------------------------------------------------------
# Filter out certain warnings to prevent tests being failed by them.
function filter_warnings() {
    python -c "import re, sys
msgs=[r'.*naked dummy tasks detected.*\n(\+\t.*\n)+',
      r'.*clock-(trigger|expire) offsets are normally positive.*\n']
file_name = sys.argv[1]
with open(file_name, 'r') as in_file:
    contents = in_file.read()
    with open(file_name + '.processed', 'w+') as out_file:
        for msg in msgs:
            contents = re.sub(msg, '', contents)
        out_file.write(contents)" "$1"
}
#-------------------------------------------------------------------------------
set_test_number $((( ((${#SUITES[@]})) * 2 )))
#-------------------------------------------------------------------------------
# Validate suites.
for suite in ${SUITES[@]}; do
    suite_name=$(sed 's/\//-/g' <<<"${suite:$ABS_PATH_LENGTH}")
    TEST_NAME="${TEST_NAME_BASE}${suite_name}"
    run_ok "${TEST_NAME}" cylc validate "${suite}" -v -v
    filter_warnings "${TEST_NAME}.stderr"
    cmp_ok "${TEST_NAME}.stderr.processed" /dev/null
done
