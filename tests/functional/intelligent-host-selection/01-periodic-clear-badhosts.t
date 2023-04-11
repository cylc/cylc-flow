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
# Test mainloop plugin periodically clears badhosts:
# * simulate remote-init failure due to SSH issues
# * ensure that "reset bad hosts" allows this task to auto "submit retry"
#   once the bad host is cleared

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 3

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the fake background job runner.
cp -r "${TEST_SOURCE_DIR}/lib" "${WORKFLOW_RUN_DIR}"

create_test_global_config '' "
    [scheduler]
        [[main loop]]
            [[[reset bad hosts]]]
                interval = PT1S
    [platforms]
        [[fake-platform]]
            hosts = localhost
            # we set the install target to make it look like a remote platform
            # (and so trigger remote-init)
            install target = fake-install-target
            # we botch the SSH command so we can simulate SSH failure
            ssh command = $HOME/cylc-run/$WORKFLOW_NAME/bin/mock-ssh
"
#-------------------------------------------------------------------------------

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play \
        --debug \
        --no-detach \
        --abort-if-any-task-fails \
        "${WORKFLOW_NAME}"

# scrape platform events from the log
sed -n \
    's/.* - \(platform: .*\)/\1/p' \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" \
    > platform-log

# check this matches expectations
# we would expect:
# * the task will attempt to remote-init
# * this will fail (because we made it fail)
# * the task will retry (because of the retry delays)
# * the task will attempt to remote-init again
# * the remote init will succeed this time
# * the task will attempt file-installation
# * file installation will fail because the install target is incorrect
cmp_ok platform-log <<__HERE__
platform: fake-platform - remote init (on localhost)
platform: fake-platform - initialisation did not complete
platform: fake-platform - remote init (on localhost)
platform: fake-platform - remote file install (on localhost)
platform: fake-platform - initialisation did not complete
platform: fake-platform - remote tidy (on localhost)
__HERE__

purge
exit 0
