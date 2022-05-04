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

export REQUIRE_PLATFORM=''
. "$(dirname "$0")/test_header"

set_test_number 5

create_test_global_config "" "
    [platforms]
        [[localh...]]
"

make_rnd_workflow

cat > "${RND_WORKFLOW_SOURCE}/flow.cylc" <<__HEREDOC__
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo
__HEREDOC__


run_ok "${TEST_NAME_BASE}-validate" cylc validate "${RND_WORKFLOW_SOURCE}"

TEST_NAME="${TEST_NAME_BASE}-cylc-install"
run_ok "${TEST_NAME}" cylc install \
    "${RND_WORKFLOW_SOURCE}" \
    --workflow-name "${RND_WORKFLOW_NAME}"
grep_ok '"localhost" settings will be defined by global.cylc[platforms][localh...]' \
    "${TEST_NAME}.stderr" -F

TEST_NAME="${TEST_NAME_BASE}-cylc-play"
run_ok "${TEST_NAME}" cylc play \
    "${RND_WORKFLOW_NAME}" \
    --no-detach

# Check that playing the workflow generates a warning only once:
grep -F '"localhost" settings will be defined by global.cylc[platforms][localh...]' "${TEST_NAME}.stdout" >&2
NO_OF_WARNS=$(grep -cF '"localhost" settings will be defined by global.cylc[platforms][localh...]' \
    "${TEST_NAME}.stderr")
TEST_NAME="${TEST_NAME_BASE}-only-1-warn"
if [[ "${NO_OF_WARNS}" == 1 ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi


# purge_rnd_workflow
exit
