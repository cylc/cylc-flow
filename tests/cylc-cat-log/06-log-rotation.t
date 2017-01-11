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
# Tests that cylc cat-log correctly handes log rotation.
. "$(dirname "$0")/test_header"
set_test_number 1
init_suite "${TEST_NAME_BASE}" '/dev/null'

# Populate its cylc-run dir with empty log files.
LOG_DIR="$(dirname "$(cylc cat-log "${SUITE_NAME}" -l)")"
mkdir -p "${LOG_DIR}"
# Note: .0 .1 .2: back compatability to old log rotation system
touch \
    "${LOG_DIR}/out.20000103T00Z" \
    "${LOG_DIR}/out.20000102T00Z" \
    "${LOG_DIR}/out.20000101T00Z" \
    "${LOG_DIR}/out.0" \
    "${LOG_DIR}/out.1" \
    "${LOG_DIR}/out.2"

# Test log rotation.
for I in {0..5}; do
    basename "$(cylc cat-log "${SUITE_NAME}" -o -l -r "${I}")"
done >'result'

cmp_ok 'result' <<'__CMP__'
out.20000103T00Z
out.20000102T00Z
out.20000101T00Z
out.0
out.1
out.2
__CMP__

purge_suite "${SUITE_NAME}"
exit
