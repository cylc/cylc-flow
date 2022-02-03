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
# Tests three different trigger cases which should all have the same result.
# 
# https://github.com/cylc/cylc-flow/issues/4644
# https://github.com/cylc/cylc-flow/issues/4619

. "$(dirname "$0")/test_header"
set_test_number 3
for cycle in 2 3 4; do
    TEST_NAME="${TEST_NAME_BASE}-${cycle}"
    install_workflow "${TEST_NAME}" "${TEST_NAME_BASE}"
    run_ok "${TEST_NAME}" \
        cylc play "${WORKFLOW_NAME}" \
            -n \
            -s "cycle=$cycle" \
            --reference-test \
            --debug
    purge
done
exit
