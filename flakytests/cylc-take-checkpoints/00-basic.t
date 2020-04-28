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
# Test checkpoint basic
. "$(dirname "$0")/test_header"

date-remove() {
    sed 's/[0-9]\+\(-[0-9]\{2\}\)\{2\}T[0-9]\{2\}\(:[0-9]\{2\}\)\{2\}Z/DATE/'
}

set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Suite reloads+inserts new task to mess up prerequisites - suite should stall
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"
cylc ls-checkpoints "${SUITE_NAME}" | date-remove >'cylc-ls-checkpoints.out'
contains_ok 'cylc-ls-checkpoints.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
1|DATE|snappy
0|DATE|latest
__OUT__

cylc ls-checkpoints "${SUITE_NAME}" 1 | date-remove >'cylc-ls-checkpoints-1.out'
contains_ok 'cylc-ls-checkpoints-1.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
1|DATE|snappy

# SUITE PARAMS (KEY|VALUE)

# TASK POOL (CYCLE|NAME|SPAWNED|STATUS|IS_HELD)
2017|t1|1|running|0
2018|t1|0|waiting|0
__OUT__

purge_suite "${SUITE_NAME}"
exit
