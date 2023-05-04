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
# Test handling of mixed up sections vs settings

. "$(dirname "$0")/test_header"

set_test_number 6

# 1. section as setting (normal)
TEST_NAME='section-as-setting-normal'
cat > 'flow.cylc' <<__HEREDOC__
[runtime]
    [[foo]]
        environment = 42
__HEREDOC__
run_fail "${TEST_NAME}-validate" cylc validate .
grep_ok  \
    'IllegalItemError: \[runtime\]\[foo\]environment - ("environment" should be a \[section\] not a setting)' \
    "${TEST_NAME}-validate.stderr"


# 2. section as setting (via upgrader)
# NOTE: if this test fails it is likely because the upgrader for "scheduling"
# has been removed, convert this to use a new deprecated section
TEST_NAME='section-as-setting-upgrader'
cat > 'flow.cylc' <<__HEREDOC__
scheduling = 22
__HEREDOC__

run_fail "${TEST_NAME}-validate" cylc validate .
grep_ok  \
    'UpgradeError: \[scheduling\] ("scheduling" should be a \[section\] not a setting' \
    "${TEST_NAME}-validate.stderr"


# 3. setting as section
TEST_NAME='setting-as-section'
cat > 'flow.cylc' <<__HEREDOC__
[scheduling]
    [[initial cycle point]]
__HEREDOC__

run_fail "${TEST_NAME}-validate" cylc validate .
grep_ok  \
    'IllegalItemError: \[scheduling\]initial cycle point - ("initial cycle point" should be a setting not a \[section\])' \
    "${TEST_NAME}-validate.stderr"
