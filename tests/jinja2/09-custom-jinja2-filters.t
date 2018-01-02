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
# basic jinja2 include and expand test
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
FILTER_DIR="${CYLC_DIR}/lib/Jinja2Filters"
CUSTOM_FILTERS=($(find "${FILTER_DIR}/" -name \*.py))
let NUM_TESTS=${#CUSTOM_FILTERS[@]}*2+1
set_test_number $NUM_TESTS
#-------------------------------------------------------------------------------
# Run doctest on all built-in Jinja2 filters.
for filter in "${CUSTOM_FILTERS[@]}"; do
    TEST_NAME="${TEST_NAME_BASE}-$(basename ${filter})"
    #1>&2 echo python -m doctest -v "${filter}"
    run_ok "${TEST_NAME}" python -m doctest "${filter}"
    sed -i /1034h/d "${TEST_NAME}.stdout"  # Remove some nasty unicode output.
    cmp_ok "${TEST_NAME}.stdout" /dev/null
done
#-------------------------------------------------------------------------------
# Run Jinja2 custom filters suite.
TEST_NAME="${TEST_NAME_BASE}"-run-filters
install_suite "${TEST_NAME_BASE}-install-filter-suite" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME}" cylc run "${SUITE_NAME}" --reference-test --debug --no-detach
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
