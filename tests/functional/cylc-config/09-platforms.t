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
# Test cylc config --platform-names and --platforms
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
cat > "global.cylc" <<__HEREDOC__
[platforms]
    [[foo]]
        job runner = slurm
        hosts = of_melkor, of_valar
    [[bar]]
        job runner = slurm
        hosts = of_orcs, of_gondor
[platform groups]
    [[FOO]]
        platforms = foo, bar
[task events]
    # Just make sure this doesn't get included
__HEREDOC__

export CYLC_CONF_PATH="${PWD}"

TEST_NAME="${TEST_NAME_BASE}-names"
run_ok "${TEST_NAME}" cylc config --platform-names
cmp_ok "${TEST_NAME}.stdout" <<__HEREDOC__
localhost
foo
bar
FOO
__HEREDOC__

cmp_ok "${TEST_NAME}.stderr" <<__HEREDOC__

Configured names are regular expressions; any match is a valid platform.
They are searched from the bottom up, until the first match is found.

Platforms
---------

Platform Groups
--------------
__HEREDOC__

TEST_NAME="${TEST_NAME_BASE}-s"
head -n 10 > just_platforms < global.cylc
run_ok "${TEST_NAME}" cylc config --platforms
cmp_ok "${TEST_NAME}.stdout" "just_platforms"

#-------------------------------------------------------------------------------
# test with no platforms or platform groups defined
rm "global.cylc"
touch "global.cylc"

TEST_NAME="${TEST_NAME_BASE}-names"
run_ok "${TEST_NAME}" cylc config --platform-names
cmp_ok "${TEST_NAME}.stdout" <<__HEREDOC__
localhost

__HEREDOC__

exit
