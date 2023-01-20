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
# Check that ``[platforms][localhost]`` is only set automatically if it
# not set in ``global.cylc``.
. "$(dirname "$0")/test_header"

set_test_number 3

# shellcheck disable=SC2016
create_test_global_config '' '
    [platforms]
        [[localh...]]
        # This should not override `localh...` in this one case, because the
        # localhost default pins it to the top of the list.
        [[localhost]]
            [[[meta]]]
                foo = "foo"
'

make_rnd_workflow

cat > "${RND_WORKFLOW_SOURCE}/flow.cylc" <<__HEREDOC__
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo
__HEREDOC__


ERR_STR='cannot be defined using a regular expression'

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${RND_WORKFLOW_SOURCE}"

TEST_NAME="${TEST_NAME_BASE}-cylc-install"
run_fail "${TEST_NAME}" cylc install \
    "${RND_WORKFLOW_SOURCE}" \
    --workflow-name "${RND_WORKFLOW_NAME}"
grep_ok "${ERR_STR}" "${TEST_NAME}.stderr" -F

purge_rnd_workflow
exit
