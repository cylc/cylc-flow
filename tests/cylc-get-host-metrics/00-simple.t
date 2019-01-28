#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA
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
# Test cylc get-host-metric.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 20
#-------------------------------------------------------------------------------
# Test each option (load, memory and disk space) individually. Use '0.10' and
# '1000000' as examples in correct format as cannot test for exact values.

# Load option.
run_ok "${TEST_NAME_BASE}-get-host-metric-load" cylc get-host-metric --load
run_ok "${TEST_NAME_BASE}-get-host-metric-l" cylc get-host-metric -l
for FILE in "${TEST_NAME_BASE}-get-host-metric-load.stdout" \
    "${TEST_NAME_BASE}-get-host-metric-l.stdout"
do
    sed -i 's/\(\s\+\)\([0-9]\+\.[0-9]\+\)\(\s*\n*,*\)/\10.10\3/g' "${FILE}"
    cmp_json_ok "${FILE}" "${FILE}" <<__OUTPUT_FORMAT__
{
    "load:1": 0.10,
    "load:5": 0.10,
    "load:15": 0.10
}
__OUTPUT_FORMAT__
done

# Memory option.
run_ok "${TEST_NAME_BASE}-get-host-metric-memory" cylc get-host-metric --memory
run_ok "${TEST_NAME_BASE}-get-host-metric-m" cylc get-host-metric -m
for FILE in "${TEST_NAME_BASE}-get-host-metric-memory.stdout" \
    "${TEST_NAME_BASE}-get-host-metric-m.stdout"
do
    sed -i 's/\(\s\+\)\([0-9]\+\)\(\s*\n*\)/\11000000\3/g' "${FILE}"
    cmp_json_ok "${FILE}" "${FILE}" <<__OUTPUT_FORMAT__
{
    "memory": 1000000
}
__OUTPUT_FORMAT__
done

# Disk space option, with a single path specified correctly.
run_ok "${TEST_NAME_BASE}-get-host-metric-disk-one" cylc get-host-metric \
--disk-space=/
sed -i 's/\(\s\+\)\([0-9]\+\)\(\s*\n*\)/\11000000\3/g' \
    "${TEST_NAME_BASE}-get-host-metric-disk-one.stdout"
cmp_json_ok "${TEST_NAME_BASE}-get-host-metric-disk-one.stdout" \
"${TEST_NAME_BASE}-get-host-metric-disk-one.stdout" <<__OUTPUT_FORMAT__
{
    "disk-space:/": 1000000
}
__OUTPUT_FORMAT__

# Disk space option, with multiple paths specified correctly.

run_ok "${TEST_NAME_BASE}-get-host-metric-disk-mult" cylc get-host-metric \
--disk-space=/,/  # Host only has root mount dir for certain; as such can only
                  # specify this safely across envs. Just check multiple paths
                  # are accepted, though they combine -> only one key:value.
sed -i 's/\(\s\+\)\([0-9]\+\)\(\s*\n*,*\)/\11000000\3/g' \
    "${TEST_NAME_BASE}-get-host-metric-disk-mult.stdout"
cmp_json_ok "${TEST_NAME_BASE}-get-host-metric-disk-mult.stdout" \
"${TEST_NAME_BASE}-get-host-metric-disk-mult.stdout" <<__OUTPUT_FORMAT__
{
    "disk-space:/": 1000000
}
__OUTPUT_FORMAT__

# Disk space option, including a bad path.
run_fail "${TEST_NAME_BASE}-get-host-metric-disk-bad" cylc get-host-metric \
--disk-space=nonsense
MESSAGE="subprocess\.CalledProcessError: Command '\['df', '-Pk', 'nonsense'\]'"
MESSAGE+=" returned non-zero exit status 1"
grep_ok "$MESSAGE" "${TEST_NAME_BASE}-get-host-metric-disk-bad.stderr"
#-------------------------------------------------------------------------------
# Test the various options in combination. Use '0.10' and '1000000' as
# examples in correct format as cannot test for exact values.

# No options; defaults to providing load and memory.
run_ok "${TEST_NAME_BASE}-get-host-metric-no-opts" cylc get-host-metric
sed -i 's/\(\s\+\)\([0-9]\+\)\(\s*\n*,*\)/\11000000\3/g' \
    "${TEST_NAME_BASE}-get-host-metric-no-opts.stdout"
sed -i 's/\(\s\+\)\([0-9]\+\.[0-9]\+\)\(\s*\n*,*\)/\10.10\3/g' \
    "${TEST_NAME_BASE}-get-host-metric-no-opts.stdout"
cmp_json_ok "${TEST_NAME_BASE}-get-host-metric-no-opts.stdout" \
"${TEST_NAME_BASE}-get-host-metric-no-opts.stdout" <<__OUTPUT_FORMAT__
{
    "load:1": 0.10,
    "load:5": 0.10,
    "load:15": 0.10,
    "memory": 1000000
}
__OUTPUT_FORMAT__

# All three options.
run_ok "${TEST_NAME_BASE}-get-host-metric-all-opts" cylc get-host-metric \
--load --memory --disk-space=/
run_ok "${TEST_NAME_BASE}-get-host-metric-all-opts-short" cylc get-host-metric \
-lm --disk-space=/
for FILE in "${TEST_NAME_BASE}-get-host-metric-all-opts.stdout" \
    "${TEST_NAME_BASE}-get-host-metric-all-opts-short.stdout"
do
    sed -i 's/\(\s\+\)\([0-9]\+\)\(\s*\n*,*\)/\11000000\3/g' "${FILE}"
    sed -i 's/\(\s\+\)\([0-9]\+\.[0-9]\+\)\(\s*\n*,*\)/\10.10\3/g' "${FILE}"
    cmp_json_ok "${FILE}" "${FILE}" <<__OUTPUT_FORMAT__
{
    "disk-space:/": 1000000,
    "load:1": 0.10000000000000001, 
    "load:5": 0.10000000000000001, 
    "load:15": 0.10000000000000001, 
    "memory": 1000000
}
__OUTPUT_FORMAT__
done
#-------------------------------------------------------------------------------
exit
