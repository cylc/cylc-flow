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

#------------------------------------------------------------------------------
# Test `cylc vr` (Validate Reinstall restart)
# Tests that VR doesn't modify the source directory for Cylc play.
# See https://github.com/cylc/cylc-flow/issues/6209

. "$(dirname "$0")/test_header"
set_test_number 9

# Setup (Run VIP, check that the play step fails in the correct way):
WORKFLOW_NAME="cylctb-x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)"
cp "${TEST_SOURCE_DIR}/vr_workflow_fail_on_play/flow.cylc" .

# Run Cylc VIP
run_fail "setup (vip)" \
    cylc vip --debug \
    --workflow-name "${WORKFLOW_NAME}" \
    --no-run-name
validate1="$(grep -Po "WARNING - vip:(.*)" "setup (vip).stderr" | awk -F ':' '{print $2}')"
play1="$(grep -Po "WARNING - play:(.*)" "setup (vip).stderr" | awk -F ':' '{print $2}')"

# Change the workflow to make the reinstall happen:
echo "" >> flow.cylc

# Run Cylc VR:
TEST_NAME="${TEST_NAME_BASE}"
run_fail "${TEST_NAME}" cylc vr "${WORKFLOW_NAME}"
validate2="$(grep -Po "WARNING - vr:(.*)" "${TEST_NAME_BASE}.stderr" | awk -F ':' '{print $2}')"
play2="$(grep -Po "WARNING - play:(.*)" "${TEST_NAME_BASE}.stderr" | awk -F ':' '{print $2}')"

# Test that the correct source directory is openened at different
# stages of Cylc VIP & VR
TEST_NAME="outputs-created"
if [[ -n $validate1 && -n $validate2 && -n $play1 && -n $play2 ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi


TEST_NAME="vip validate and play operate on different folders"
if [[ $validate1 != "${play1}" ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

TEST_NAME="vr & vip validate operate on the same folder"
if [[ $validate1 == "${validate2}" ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

TEST_NAME="vr validate and play operate on different folders"
if [[ $validate2 != "${play2}" ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

TEST_NAME="vip play loads from a cylc-run subdir"
if [[ "${play2}" =~ cylc-run ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

TEST_NAME="vr play loads from a cylc-run subdir"
if [[ "${play2}" =~ cylc-run ]]; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

# Clean Up:
run_ok "${TEST_NAME_BASE}-stop cylc stop ${WORKFLOW_NAME} --now --now"
purge
exit 0
