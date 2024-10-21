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
# Test cylc config can dump json files.
# n.b. not heavily tested because most of this functionality
# is from Standard library json.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 9
#-------------------------------------------------------------------------------

# Test that option parser errors if incompat options given:
cylc config --json --platforms 2> err
named_grep_ok "${TEST_NAME_BASE}.CLI-one-incompat-item" \
    "--json incompatible with --platforms" \
    err

cylc config --json --platforms --platform-names 2> err
named_grep_ok "${TEST_NAME_BASE}.CLI-two-incompat-items" \
    "--json incompatible with --platform-names or --platforms" \
    err

cylc config --json --platforms --platform-names --print-hierarchy 2> err
named_grep_ok "${TEST_NAME_BASE}.CLI-three-incompat-items" \
    "--json incompatible with --print-hierarchy or --platform-names or --platforms" \
    err


# Test the global.cylc
TEST_NAME="${TEST_NAME_BASE}-global"

cat > "global.cylc" <<__HEREDOC__
[platforms]
    [[golders_green]]
        [[[meta]]]
            can = "Test lots of things"
            because = metadata, is, not, fussy
            number = 99
__HEREDOC__

export CYLC_CONF_PATH="${PWD}"
run_ok "${TEST_NAME}" cylc config --json --one-line
cmp_ok "${TEST_NAME}.stdout" <<__HERE__
{"platforms": {"golders_green": {"meta": {"can": "Test lots of things", "because": "metadata, is, not, fussy", "number": "99"}}}}
__HERE__

# Test a flow.cylc
TEST_NAME="${TEST_NAME_BASE}-workflow"

cat > "flow.cylc" <<__HERE__
[scheduling]
    [[graph]]
        P1D = foo

[runtime]
    [[foo]]
__HERE__

run_ok "${TEST_NAME}" cylc config . --json --icp 1000
cmp_ok "${TEST_NAME}.stdout" <<__HERE__
{
    "scheduling": {
        "graph": {
            "P1D": "foo"
        },
        "initial cycle point": "1000"
    },
    "runtime": {
        "root": {},
        "foo": {
            "completion": "succeeded"
        }
    }
}
__HERE__

# Test an empty global.cylc to check:
# * item selection
# * null value setting
# * showing defaults
TEST_NAME="${TEST_NAME_BASE}-defaults-item-null-value"
echo "" > global.cylc
export CYLC_CONF_PATH="${PWD}"

run_ok "${TEST_NAME}" cylc config \
    -i '[scheduler][mail]' \
    --json \
    --defaults \
    --null-value='zilch'

cmp_ok "${TEST_NAME}.stdout" <<__HERE__
{
    "from": "zilch",
    "smtp": "zilch",
    "to": "zilch",
    "footer": "zilch",
    "task event batch interval": 300.0
}
__HERE__
