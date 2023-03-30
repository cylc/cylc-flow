#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
init_workflow "${TEST_NAME_BASE}" '/dev/null'

# Populate its cylc-run dir with empty log files.
LOG_DIR="$HOME/cylc-run/$WORKFLOW_NAME/log/scheduler"
mkdir -p "${LOG_DIR}"
touch -t '201001011200.00' "${LOG_DIR}/01-start-01.log"
touch -t '201001011200.01' "${LOG_DIR}/02-start-01.log"
touch -t '201001011200.02' "${LOG_DIR}/03-restart-02.log"

# Test log rotation.
for I in {0..2}; do
    basename "$(cylc cat-log "${WORKFLOW_NAME}" -m p -r "${I}")"
done >'result'

cmp_ok 'result' <<'__CMP__'
03-restart-02.log
02-start-01.log
01-start-01.log
__CMP__

purge
exit
