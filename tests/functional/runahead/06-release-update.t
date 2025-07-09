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
# Test that the datastore is updated when runahead tasks are released.
# GitHub #1981
. "$(dirname "$0")/test_header"
set_test_number 3
install_workflow "${TEST_NAME_BASE}" 'release-update'
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
cylc play --debug --no-detach "${WORKFLOW_NAME}" 1>'out' 2>&1 &
CYLC_RUN_PID="$!"
poll_workflow_running
YYYY="$(date +%Y)"
NEXT1=$(( YYYY + 1 ))
poll_grep_workflow_log -E "${NEXT1}/bar.* added to the n=0 window"

# sleep a little to allow the datastore to update (`cylc dump` sees the
# datastore) TODO can we avoid this flaky sleep somehow?
sleep 10

# (gratuitous use of --flows for test coverage)
cylc dump -l --flows -t "${WORKFLOW_NAME}" | awk '{print $1 $2 $3 $7}' >'log'

# The scheduler task pool should contain:
#   NEXT1/foo - waiting on clock trigger
#   NEXT1/bar - waiting, partially satisfied
# The n=1 data store should also contain:
#   YYYY/bar - succeeded

cmp_ok 'log' - <<__END__
bar,$NEXT1,waiting,[1]
foo,$NEXT1,waiting,[1]
__END__

run_ok "${TEST_NAME_BASE}-stop" \
    cylc stop --max-polls=10 --interval=6 "${WORKFLOW_NAME}"
if ! wait "${CYLC_RUN_PID}" 1>'/dev/null' 2>&1; then
    cat 'out' >&2
fi
#-------------------------------------------------------------------------------
purge
exit
