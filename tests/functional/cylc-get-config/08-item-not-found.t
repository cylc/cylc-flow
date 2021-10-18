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
# Test cylc config
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
cat >>'global.cylc' <<__HERE__
[platforms]
    [[foo]]
__HERE__

OLD="$CYLC_CONF_PATH"
export CYLC_CONF_PATH="${PWD}"

# Control Run
run_ok "${TEST_NAME_BASE}-ok" cylc config -i "[platforms]foo"

# If item not settable in config (platforms is mis-spelled):
run_fail "${TEST_NAME_BASE}-not-in-config-spec" cylc config -i "[platfroms]foo"
grep_ok "NotAConfigItemError" "${TEST_NAME_BASE}-not-in-config-spec.stderr"

# If item not defined, item not found.
run_fail "${TEST_NAME_BASE}-not-defined" cylc config -i "[scheduler]"
grep_ok "ItemNotFoundError" "${TEST_NAME_BASE}-not-defined.stderr"

# If item settable in config, item not found.
run_fail "${TEST_NAME_BASE}-not-defined__MULTI__" cylc config -i "[platforms]bar"
grep_ok "ItemNotFoundError" "${TEST_NAME_BASE}-not-defined__MULTI__.stderr"

rm global.cylc
export CYLC_CONF_PATH="$OLD"

exit
