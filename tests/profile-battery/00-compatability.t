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
# Ensure that any changes to cylc haven't broken the profile-battery command
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
# Check the format of `cylc version --long`.
run_ok "${TEST_NAME_BASE}-cylc-version" python -c "
import os
import sys
os.chdir('${CYLC_DIR}/lib')
from cylc.profiling import get_cylc_directory
if get_cylc_directory() != '${CYLC_DIR}':
    sys.exit(1)
"
#-------------------------------------------------------------------------------
# Check for hello-world suite and that the cylc list command is still instated.
TEST_NAME="${TEST_NAME_BASE}-cylc-list-hello-world-suite"
run_ok "${TEST_NAME}" cylc list "${CYLC_DIR}/dev/suites/hello-world"
cmp_ok "${TEST_NAME}.stdout" "${TEST_NAME}.stdout" "hello-world"
#-------------------------------------------------------------------------------
# Run the test experiment.
TEST_NAME="${TEST_NAME_BASE}-run-test-experiment"
LOG_DIR="${TEST_LOG_DIR}/${TEST_NAME}"
mkdir "${LOG_DIR}" -p
RET_CODE=0
cylc profile-battery -e 'test' -v 'HEAD' --test \
    >"${LOG_DIR}.log" \
    2>"${LOG_DIR}.stderr" \
    || RET_CODE=$?
if [[ ${RET_CODE} == 0 ]]
then
    ok "${TEST_NAME}"
elif [[ ${RET_CODE} == 2 ]]
then
    echo "Test requires git repository." >&2
    skip 1
else
    fail "${TEST_NAME}"
    # Move/rename profiling files so they will be cat'ed out by travis-ci.
    while read; do
        file_path="${REPLY}"
        file_prefix=$(basename ${file_path})
        profile_dir=$(dirname ${file_path})
        profile_files=($(find "${profile_dir}" -type f -name "${file_prefix}*" \
                2>/dev/null))
        for profile_file in ${profile_files[@]}; do
            mv "${profile_file}" "${LOG_DIR}/$(basename ${profile_file})-err"
        done
    done < <(sed -n 's/Profile files:\(.*\)/\1/p' "${LOG_DIR}.stderr")
    mv "${LOG_DIR}.log" "${LOG_DIR}.profile-battery-log-err"
fi
