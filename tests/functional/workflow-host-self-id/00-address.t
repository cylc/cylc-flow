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
# Ensure that workflow contact env host IP address is defined

. "$(dirname "$0")/test_header"
set_test_number 2
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

get_local_ip_address() {
    python3 - "$1" <<'__PYTHON__'
import sys
from cylc.flow.hostuserutil import get_local_ip_address
sys.stdout.write("%s\n" % get_local_ip_address(sys.argv[1]))
__PYTHON__
}

#-------------------------------------------------------------------------------
MY_INET_TARGET=$(cylc config -d '--item=[scheduler][host self-identification]target')
MY_HOST_IP="$(get_local_ip_address "${MY_INET_TARGET}")"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}" --set="MY_HOST_IP='${MY_HOST_IP}'"

create_test_global_config '' '
[scheduler]
    [[host self-identification]]
        method = address'
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}" \
    --set="MY_HOST_IP='${MY_HOST_IP}'"
#-------------------------------------------------------------------------------

purge
exit
