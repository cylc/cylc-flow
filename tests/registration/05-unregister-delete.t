#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test unregister --delete.

. "$(dirname "$0")/test_header"
set_test_number 13

UUID="$(uuidgen)"

create_and_register_name() {
    local NAME="$1"
    mkdir "${NAME}"
    cat >"${NAME}/suite.rc" <<'__SUITERC__'
[scheduling]
    [[dependencies]]
        graph = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__
    cylc register "${UUID}-${NAME}" "${PWD}/${NAME}" 1>'/dev/null'
}

for NAME in 'foo' 'bar' 'baz' 'qux'; do
    create_and_register_name "${NAME}"
done

run_ok "${TEST_NAME_BASE}-force" cylc unregister --delete --force "${UUID}-.*"
cmp_ok "${TEST_NAME_BASE}-force.stdout" <<__OUT__
UNREGISTER ${UUID}-bar:${PWD}/bar
UNREGISTER ${UUID}-baz:${PWD}/baz
UNREGISTER ${UUID}-foo:${PWD}/foo
UNREGISTER ${UUID}-qux:${PWD}/qux
4 suite(s) unregistered.
DELETE "${PWD}/bar"
DELETE "${PWD}/baz"
DELETE "${PWD}/foo"
DELETE "${PWD}/qux"
__OUT__
cmp_ok "${TEST_NAME_BASE}-force.stderr" <'/dev/null'

for NAME in 'foo' 'bar' 'baz' 'qux'; do
    create_and_register_name "${NAME}"
done

run_ok "${TEST_NAME_BASE}-all" \
    cylc unregister --delete "${UUID}-.*" <<<'a'
cmp_ok "${TEST_NAME_BASE}-all.stdout" <<__OUT__
UNREGISTER ${UUID}-bar:${PWD}/bar
UNREGISTER ${UUID}-baz:${PWD}/baz
UNREGISTER ${UUID}-foo:${PWD}/foo
UNREGISTER ${UUID}-qux:${PWD}/qux
4 suite(s) unregistered.
REALLY DELETE "${PWD}/bar"? (y/n/a) DELETE "${PWD}/bar"
DELETE "${PWD}/baz"
DELETE "${PWD}/foo"
DELETE "${PWD}/qux"
__OUT__
cmp_ok "${TEST_NAME_BASE}-all.stderr" <'/dev/null'

for NAME in 'foo' 'bar' 'baz' 'qux'; do
    create_and_register_name "${NAME}"
done

run_ok "${TEST_NAME_BASE}-yes-4" \
    cylc unregister --delete "${UUID}-.*" <<'__YES__'
y
y
y
y
__YES__
cmp_ok "${TEST_NAME_BASE}-yes-4.stdout" <<__OUT__
UNREGISTER ${UUID}-bar:${PWD}/bar
UNREGISTER ${UUID}-baz:${PWD}/baz
UNREGISTER ${UUID}-foo:${PWD}/foo
UNREGISTER ${UUID}-qux:${PWD}/qux
4 suite(s) unregistered.
REALLY DELETE "${PWD}/bar"? (y/n/a) DELETE "${PWD}/bar"
REALLY DELETE "${PWD}/baz"? (y/n/a) DELETE "${PWD}/baz"
REALLY DELETE "${PWD}/foo"? (y/n/a) DELETE "${PWD}/foo"
REALLY DELETE "${PWD}/qux"? (y/n/a) DELETE "${PWD}/qux"
__OUT__
cmp_ok "${TEST_NAME_BASE}-yes-4.stderr" <'/dev/null'

for NAME in 'foo' 'bar' 'baz' 'qux'; do
    create_and_register_name "${NAME}"
done

run_ok "${TEST_NAME_BASE}-yes-3" \
    cylc unregister --delete "${UUID}-.*" <<'__YES__'
y
y
n
y
__YES__
cmp_ok "${TEST_NAME_BASE}-yes-3.stdout" <<__OUT__
UNREGISTER ${UUID}-bar:${PWD}/bar
UNREGISTER ${UUID}-baz:${PWD}/baz
UNREGISTER ${UUID}-foo:${PWD}/foo
UNREGISTER ${UUID}-qux:${PWD}/qux
4 suite(s) unregistered.
REALLY DELETE "${PWD}/bar"? (y/n/a) DELETE "${PWD}/bar"
REALLY DELETE "${PWD}/baz"? (y/n/a) DELETE "${PWD}/baz"
REALLY DELETE "${PWD}/foo"? (y/n/a) REALLY DELETE "${PWD}/qux"? (y/n/a) DELETE "${PWD}/qux"
__OUT__
cmp_ok "${TEST_NAME_BASE}-yes-3.stderr" <'/dev/null'
exists_ok "${PWD}/foo"

exit
