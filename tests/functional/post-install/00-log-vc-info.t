#!/usr/bin/env bash
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
# Test logging of source dir version control information occurs post install

. "$(dirname "$0")/test_header"
if ! command -v 'git' > /dev/null; then
    skip_all 'git not installed'
fi
set_test_number 4

make_rnd_suite
cd "${RND_SUITE_SOURCE}" || exit 1
cat > 'flow.cylc' << __FLOW__
[scheduling]
    [[graph]]
        R1 = foo
__FLOW__

git init
git add 'flow.cylc'
git commit -am 'Initial commit'

run_ok "${TEST_NAME_BASE}-install" cylc install

VCS_INFO_FILE="${RND_SUITE_RUNDIR}/runN/log/version/vcs.conf"
exists_ok "$VCS_INFO_FILE"
# Basic check, unit tests cover this in more detail:
contains_ok "$VCS_INFO_FILE" <<< 'version control system = "git"'

DIFF_FILE="${RND_SUITE_RUNDIR}/runN/log/version/uncommitted.diff"
exists_ok "$DIFF_FILE"  # Expected to be empty but should exist

purge_rnd_suite
