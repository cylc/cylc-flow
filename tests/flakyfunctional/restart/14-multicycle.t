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
# Test restarting a suite with multi-cycle tasks and interdependencies.
if [[ -z "${TEST_DIR:-}" ]]; then
    . "$(dirname "$0")/test_header"
fi
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
export TEST_DIR
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
if ! command -v 'sqlite3' > /dev/null; then
    skip 5 'sqlite3 not installed?'
    purge_suite "${SUITE_NAME}"
    exit 0
fi
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-restart-run" \
    cylc restart --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
cmp_ok "${TEST_DIR}/pre-restart-db" <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|0||waiting
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|0||waiting
output_states|20130925T0000Z|0||waiting
__DB_DUMP__
contains_ok "${TEST_DIR}/post-restart-db" <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|0||waiting
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|0||waiting
shutdown|20130925T0000Z|1|1|succeeded
__DB_DUMP__
"${TEST_SOURCE_DIR}/bin/ctb-select-task-states" "${SUITE_RUN_DIR}" \
    > "${TEST_DIR}/db"
cmp_ok "${TEST_DIR}/db" <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|1|1|succeeded
bar|20130925T1200Z|1|1|succeeded
bar|20130926T0000Z|1|1|succeeded
bar|20130926T1200Z|0||waiting
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|1|1|succeeded
foo|20130925T1200Z|1|1|succeeded
foo|20130926T0000Z|1|1|succeeded
foo|20130926T1200Z|0||waiting
output_states|20130925T0000Z|1|1|succeeded
shutdown|20130925T0000Z|1|1|succeeded
__DB_DUMP__
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
