#!/usr/bin/env bash
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
# Tests that cylc cat-log correctly handles log rotation.
. "$(dirname "$0")/test_header"
set_test_number 1
init_suite "${TEST_NAME_BASE}" '/dev/null'

# Populate its cylc-run dir with empty log files.
LOG_DIR="$(dirname "$(cylc cat-log -m p "${SUITE_NAME}")")"
mkdir -p "${LOG_DIR}"
# Note: .0 .1 .2: back compatibility to old log rotation system
touch -t '201001011200.00' "${LOG_DIR}/log.20000103T00Z"
touch -t '201001011200.01' "${LOG_DIR}/log.20000102T00Z"
touch -t '201001011200.02' "${LOG_DIR}/log.20000101T00Z"
touch -t '201001011200.03' "${LOG_DIR}/log.0"
touch -t '201001011200.04' "${LOG_DIR}/log.1"
touch -t '201001011200.05' "${LOG_DIR}/log.2"

# Test log rotation.
for I in {0..5}; do
    basename "$(cylc cat-log "${SUITE_NAME}" -m p -r "${I}")"
done >'result'

cmp_ok 'result' <<'__CMP__'
log.2
log.1
log.0
log.20000101T00Z
log.20000102T00Z
log.20000103T00Z
__CMP__

purge_suite "${SUITE_NAME}"
exit
