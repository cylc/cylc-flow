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
set_test_number 9
#-------------------------------------------------------------------------------
cat >>'global.cylc' <<__HERE__
[platforms]
    [[foo]]
__HERE__

OLD="$CYLC_CONF_PATH"
export CYLC_CONF_PATH="${PWD}"

# Control Run
run_ok "${TEST_NAME_BASE}-ok" cylc config -i "[platforms][foo]"

# If item not settable in config (platforms is mis-spelled):
run_fail "${TEST_NAME_BASE}-not-in-config-spec" cylc config -i "[platfroms][foo]"
cmp_ok "${TEST_NAME_BASE}-not-in-config-spec.stderr" << __HERE__
InvalidConfigError: "platfroms" is not a valid configuration for global.cylc.
__HERE__

# If item settable in config but not set.
run_fail "${TEST_NAME_BASE}-not-defined" cylc config -i "[scheduler]"
cmp_ok "${TEST_NAME_BASE}-not-defined.stderr" << __HERE__
ItemNotFoundError: You have not set "scheduler" in this config.
__HERE__

run_fail "${TEST_NAME_BASE}-not-defined-2" cylc config -i "[platforms][bar]"
cmp_ok "${TEST_NAME_BASE}-not-defined-2.stderr" << __HERE__
ItemNotFoundError: You have not set "[platforms]bar" in this config.
__HERE__

run_fail "${TEST_NAME_BASE}-not-defined-3" cylc config -i "[platforms][foo]hosts"
cmp_ok "${TEST_NAME_BASE}-not-defined-3.stderr" << __HERE__
ItemNotFoundError: You have not set "[platforms][foo]hosts" in this config.
__HERE__

rm global.cylc
export CYLC_CONF_PATH="$OLD"
