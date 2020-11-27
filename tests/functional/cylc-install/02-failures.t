#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Test workflow installation failures


export RND_SUITE_NAME
export RND_SUITE_SOURCE
export RND_SUITE_RUNDIR

function make_rnd_suite() {
    # Create a randomly-named suite source directory.
    # Define its run directory.
    RND_SUITE_NAME=x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)
    RND_SUITE_SOURCE="$PWD/${RND_SUITE_NAME}"
    mkdir -p "${RND_SUITE_SOURCE}"
    touch "${RND_SUITE_SOURCE}/flow.cylc"
    RND_SUITE_RUNDIR="${RUN_DIR}/${RND_SUITE_NAME}"
}

function purge_rnd_suite() {
    # Remove the suite source created by make_rnd_suite().
    # And remove its run-directory too.
    RND_SUITE_SOURCE=${1:-$RND_SUITE_SOURCE}
    RND_SUITE_RUNDIR=${2:-$RND_SUITE_RUNDIR}
    rm -rf "${RND_SUITE_SOURCE}"
    rm -rf "${RND_SUITE_RUNDIR}"
}

. "$(dirname "$0")/test_header"
set_test_number 16

# Test fail no suite source dir
TEST_NAME="${TEST_NAME_BASE}-nodir"
make_rnd_suite
rm -rf "${RND_SUITE_SOURCE}"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_NAME}" --no-run-name -C "${RND_SUITE_SOURCE}" 
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no flow.cylc or suite.rc in ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite


# Test fail no flow.cylc or suite.rc file
TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
make_rnd_suite
rm -f "${RND_SUITE_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_NAME}" -C "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no flow.cylc or suite.rc in ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite

# Test cylc install fails when given flow-name that is an absolute path
TEST_NAME="${TEST_NAME_BASE}-no-abs-path-flow-name"
make_rnd_suite
rm -f "${RND_SUITE_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_SOURCE}" -C "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: Workflow name cannot be an absolute path: ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite


# Test cylc install can not be run from within the cylc-run directory
TEST_NAME="${TEST_NAME_BASE}-forbid-cylc-run-dir-install"
BASE_NAME="cylctb-${CYLC_TEST_TIME_INIT}"
mkdir -p ${RUN_DIR}/${BASE_NAME}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME} && cd $_
touch flow.cylc
run_fail "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: Installation failed. Source directory should not be in ${RUN_DIR}
__ERR__
rm -rf ${RUN_DIR}/${BASE_NAME}


# Test source dir can not contain '_cylc-install, log, share, work' dirs
for DIR in 'work' 'share' 'log' '_cylc-install'; do
    TEST_NAME="${TEST_NAME_BASE}-${DIR}-forbidden-in-source"
    make_rnd_suite
    pushd "${RND_SUITE_SOURCE}" || exit 1
    mkdir ${DIR}
    run_fail "${TEST_NAME}" cylc install
    contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: Installation failed. - ${DIR} exists in source directory.
__ERR__
    popd || exit 1
    purge_rnd_suite
done
