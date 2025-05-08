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

# "cylc set" proposal examples: 7 - Check spawning a parentless task without ignoring xtriggers.
# https://cylc.github.io/cylc-admin/proposal-cylc-set.html#7-spawning-parentless-tasks

. "$(dirname "$0")/test_header"
set_test_number 3

install_and_validate
REFTEST_OPTS="--start-task=1800/a" reftest_run

grep_workflow_log_ok "${TEST_NAME_BASE}-clock" "xtrigger succeeded: wall_clock"

purge
