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
# Test restart from a checkpoint before a reload
. "$(dirname "$0")/test_header"

date-remove() {
    sed 's/[0-9]\+\(-[0-9]\{2\}\)\{2\}T[0-9]\{2\}\(:[0-9]\{2\}\)\{2\}Z/DATE/'
}

set_test_number 8

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
cp -p 'suite.rc' 'suite1.rc'

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Suite reloads+inserts new task to mess up prerequisites - suite should stall
suite_run_fail "${TEST_NAME_BASE}-run" \
    timeout 120 cylc run "${SUITE_NAME}" --debug --no-detach
cylc ls-checkpoints "${SUITE_NAME}" | date-remove >'cylc-ls-checkpoints.out'
contains_ok 'cylc-ls-checkpoints.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
1|DATE|reload-init
2|DATE|reload-done
0|DATE|latest
__OUT__

cylc ls-checkpoints "${SUITE_NAME}" 1 | date-remove >'cylc-ls-checkpoints-1.out'
contains_ok 'cylc-ls-checkpoints-1.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
1|DATE|reload-init

# SUITE PARAMS (KEY|VALUE)
is_held|1

# BROADCAST STATES (POINT|NAMESPACE|KEY|VALUE)
2017|t1|script|true

# TASK POOL (CYCLE|NAME|SPAWNED|STATUS|IS_HELD)
2017|t1|1|running|1
2018|t1|0|waiting|1
__OUT__
cylc ls-checkpoints "${SUITE_NAME}" 2 | date-remove >'cylc-ls-checkpoints-2.out'
contains_ok 'cylc-ls-checkpoints-2.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
2|DATE|reload-done

# SUITE PARAMS (KEY|VALUE)
is_held|1

# BROADCAST STATES (POINT|NAMESPACE|KEY|VALUE)
2017|t1|script|true

# TASK POOL (CYCLE|NAME|SPAWNED|STATUS|IS_HELD)
2017|t1|1|running|1
2018|t1|0|waiting|1
__OUT__
cylc ls-checkpoints "${SUITE_NAME}" 0 | date-remove >'cylc-ls-checkpoints-0.out'
contains_ok 'cylc-ls-checkpoints-0.out' <<'__OUT__'
#######################################################################
# CHECKPOINT ID (ID|TIME|EVENT)
0|DATE|latest

# SUITE PARAMS (KEY|VALUE)

# BROADCAST STATES (POINT|NAMESPACE|KEY|VALUE)
2017|t1|script|true

# TASK POOL (CYCLE|NAME|SPAWNED|STATUS|IS_HELD)
2017|t2|1|failed|0
2018|t1|0|waiting|0
2018|t2|0|waiting|0
__OUT__

# Restart should stall in exactly the same way
suite_run_fail "${TEST_NAME_BASE}-restart-1" \
    timeout 60 cylc restart "${SUITE_NAME}" --debug --no-detach

# Restart from a checkpoint before the reload should allow the suite to proceed
# normally.
cp -p 'suite1.rc' 'suite.rc'
suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    timeout 120 cylc restart "${SUITE_NAME}" \
    --checkpoint=1 --debug --no-detach --reference-test

purge_suite "${SUITE_NAME}"
exit
