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

# Test event handlers when killing running/submitted/preparing tasks.
# Any downstream tasks that depend on the `:submit-fail`/`:fail` outputs
# SHOULD run.
# Handlers for the `submission failed`/`failed` events SHOULD run.

export REQUIRE_PLATFORM='runner:at'
. "$(dirname "$0")/test_header"
set_test_number 5

# Create platform that ensures job will be in submitted state for long enough
create_test_global_config '' "
[platforms]
    [[old_street]]
        job runner = at
        job runner command template = at now + 5 minutes
        hosts = localhost
        install target = localhost
"

install_and_validate
reftest_run

grep_workflow_log_ok "grep-a" "[(('event-handler-00', 'failed'), 1) out] 1/a" -F

for task in b c; do
    grep_workflow_log_ok "grep-${task}" \
        "[(('event-handler-00', 'submission failed'), 1) out] 1/${task}" -F
done

purge
