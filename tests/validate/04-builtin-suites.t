#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
SUITES=($(find "${CYLC_DIR}/"{etc/examples,etc/dev-suites} -name 'suite.rc' \
    | grep -v 'empy' ))  # TODO - don't validate empy suites see: #2958
ABS_PATH_LENGTH=${#CYLC_DIR}
#-------------------------------------------------------------------------------
# Filter out certain warnings to prevent tests being failed by them.
function filter_warnings() {
    python3 - "$@" <<'__PYTHON__'
import re, sys
msgs = [
    r'(?:INFO|DEBUG) - .*\n(\t.*\n)*',
    r'.*naked dummy tasks detected.*\n(\t.*\n)+',
    r'.*clock-(trigger|expire) offsets are normally positive.*\n']
file_name = sys.argv[1]
with open(file_name, 'r') as in_file:
    contents = in_file.read()
    with open(file_name + '.processed', 'w+') as out_file:
        for msg in msgs:
            contents = re.sub(msg, '', contents)
        out_file.write(contents)
__PYTHON__
}
#-------------------------------------------------------------------------------
set_test_number $((( ((${#SUITES[@]})) * 2 )))
#-------------------------------------------------------------------------------
# Validate suites.
NO_EMPY=true
if cylc check-software 2>'/dev/null' | grep -q '^Python:EmPy.*([^-]*)$'; then
    NO_EMPY=false
fi
for suite in ${SUITES[@]}; do
    suite_name=$(sed 's/\//-/g' <<<"${suite:$ABS_PATH_LENGTH}")
    TEST_NAME="${TEST_NAME_BASE}${suite_name}"
    if "${NO_EMPY}" && grep -qi '^#!empy' < <(head -1 "${suite}"); then
        skip 2 "${TEST_NAME}: EmPy not installed"
        continue
    fi
    run_ok "${TEST_NAME}" cylc validate "${suite}" -v
    filter_warnings "${TEST_NAME}.stderr"
    cmp_ok "${TEST_NAME}.stderr.processed" /dev/null
done
