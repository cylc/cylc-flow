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
# Check that platform names are not treated as host names. E.g. a platform
# name starting with "localhost" should not be treated as localhost.
# https://github.com/cylc/cylc-flow/issues/5342
. "$(dirname "$0")/test_header"

set_test_number 2

# shellcheck disable=SC2016
create_test_global_config '' '
[platforms]
    [[localhost_spice]]
        hosts = unreachable
'

make_rnd_workflow

cat > "${RND_WORKFLOW_SOURCE}/flow.cylc" <<__HEREDOC__
[scheduler]
    [[events]]
        stall timeout = PT0S
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        platform = localhost_spice
__HEREDOC__

ERR_STR='Unable to find valid host for localhost_spice'

TEST_NAME="${TEST_NAME_BASE}-vip-workflow"
run_fail "${TEST_NAME}" cylc vip "${RND_WORKFLOW_SOURCE}" --no-detach
grep_ok "${ERR_STR}" \
    "${TEST_NAME}.stderr" -F

purge_rnd_workflow
exit
