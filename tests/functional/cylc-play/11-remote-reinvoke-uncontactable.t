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

# Test that remote reinvocation exits non-zero if the remote host is
# uncontactable.
# https://github.com/cylc/cylc-flow/pull/6745
# Ideally we would test with multiple hosts in [scheduler][run hosts]available
# to ensure each is tried, but that is not feasible.

export REQUIRE_PLATFORM='loc:remote fs:shared'
# (We need a valid remote host; the platform itself is not used)

. "$(dirname "$0")/test_header"
set_test_number 2

# create an SSH config that will fail to connect to a valid host
mock_ssh_config_file="/var/tmp/cylc-test-ssh-config"
cat > "${mock_ssh_config_file}" << __EOF__
Host ${CYLC_TEST_HOST}*
    User BorkedMushroom25
__EOF__

create_test_global_config "" "
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST}
        ranking =
[platforms]
    [[localhost]]
        ssh command = ssh -oBatchMode=yes -oStrictHostKeyChecking=no -F ${mock_ssh_config_file}
"

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = a
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_fail "$TEST_NAME" \
    cylc play "${WORKFLOW_NAME}" --no-detach --mode=simulation

grep_ok "Cylc could not establish SSH connection to the run hosts" \
    "${TEST_NAME}.stderr"
