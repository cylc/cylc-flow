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
# Test that the state summary is updated when runahead tasks are released.
# GitHub #1981
. "$(dirname "$0")/test_header"
set_test_number 3
install_suite "${TEST_NAME_BASE}" 'release-update'
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
cylc run --debug --no-detach "${SUITE_NAME}" 1>'out' 2>&1 &
CYLC_RUN_PID="$!"
poll_suite_running
YYYY="$(date +%Y)"
NEXT1=$(( YYYY + 1 ))
poll_grep_suite_log -F "[bar.${NEXT1}] -released to the task pool"

cylc dump -t "${SUITE_NAME}" | awk '{print $1 $2 $3}' >'log'
cmp_ok 'log' - <<__END__
bar,$NEXT1,waiting,
foo,$NEXT1,waiting,
__END__

run_ok "${TEST_NAME_BASE}-stop" \
    cylc stop --max-polls=10 --interval=6 "${SUITE_NAME}"
if ! wait "${CYLC_RUN_PID}" 1>'/dev/null' 2>&1; then
    cat 'out' >&2
fi
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
