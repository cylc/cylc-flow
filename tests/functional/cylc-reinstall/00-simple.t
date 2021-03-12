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
# Test workflow re-installation
. "$(dirname "$0")/test_header"
set_test_number 36

# Test basic cylc reinstall, named run given
TEST_NAME="${TEST_NAME_BASE}-basic-named-run"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__
run_ok "basic-reinstall" cylc reinstall "${RND_SUITE_NAME}/run1"
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_SUITE_NAME}/run1 from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1" "${REINSTALL_LOG}"

popd || exit 1
purge_rnd_suite

# Test basic cylc reinstall, named run (including ``flow.cylc``) given
TEST_NAME="${TEST_NAME_BASE}-flow-as-arg"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc install
run_ok "${TEST_NAME}-reinstall" cylc reinstall "${RND_SUITE_NAME}/run1/flow.cylc"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_SUITE_NAME}/run1 from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1" "${REINSTALL_LOG}"
popd || exit 1
purge_rnd_suite

# Test basic cylc reinstall, named run (including suite.rc) given
TEST_NAME="${TEST_NAME_BASE}-suite.rc-as-arg"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
rm -rf flow.cylc
touch suite.rc
run_ok "${TEST_NAME}" cylc install
run_ok "${TEST_NAME}-reinstall-suite.rc" cylc reinstall "${RND_SUITE_NAME}/run1/suite.rc"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_SUITE_NAME}/run1 from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1" "${REINSTALL_LOG}"
popd || exit 1
purge_rnd_suite

# Test install/reinstall executed from elsewhere in filesystem
TEST_NAME="${TEST_NAME_BASE}-named-flow"
make_rnd_suite
pushd "${TMPDIR}" || exit 1
run_ok "${TEST_NAME}-install" cylc install -C "${RND_SUITE_SOURCE}" --flow-name="${RND_SUITE_NAME}"
contains_ok "${TEST_NAME}-install.stdout" <<__OUT__
INSTALLED ${RND_SUITE_NAME} from ${RND_SUITE_SOURCE} -> ${RUN_DIR}/${RND_SUITE_NAME}/run1
__OUT__
run_ok "${TEST_NAME}-reinstall" cylc reinstall "${RND_SUITE_NAME}/run1"
contains_ok "${TEST_NAME}-reinstall.stdout" <<__OUT__
REINSTALLED $RND_SUITE_NAME/run1 from ${RND_SUITE_SOURCE} -> ${RUN_DIR}/${RND_SUITE_NAME}/run1
__OUT__
popd || exit 1
purge_rnd_suite
rm -rf "${RUN_DIR:?}/${RND_SUITE_NAME}/"

# Test cylc reinstall succeeds if suite.rc file in source dir
TEST_NAME="${TEST_NAME_BASE}-no-flow-file"
make_rnd_suite
rm -f "${RND_SUITE_SOURCE}/flow.cylc"
touch "${RND_SUITE_SOURCE}/suite.rc"
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_NAME}" -C "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__
# test symlink not made in source dir
exists_fail "flow.cylc"
# test symlink correctly made in run dir
pushd "${RND_SUITE_RUNDIR}/run1" || exit 1
exists_ok "flow.cylc"
if [[ $(readlink "${RND_SUITE_RUNDIR}/run1/flow.cylc") == "${RND_SUITE_RUNDIR}/run1/suite.rc" ]] ; then
    ok "symlink.suite.rc"
else
    fail "symlink.suite.rc"
fi

INSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*.log')"
grep_ok "The filename \"suite.rc\" is deprecated in favour of \"flow.cylc\". Symlink created." "${INSTALL_LOG}"
rm -rf flow.cylc
run_ok "${TEST_NAME}-reinstall" cylc reinstall "${RND_SUITE_NAME}/run1"
exists_ok "${RND_SUITE_RUNDIR}/run1/flow.cylc"
if [[ $(readlink "${RND_SUITE_RUNDIR}/run1/flow.cylc") == "${RND_SUITE_RUNDIR}/run1/suite.rc" ]] ; then
    ok "symlink.suite.rc"
else
    fail "symlink.suite.rc"
fi
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "The filename \"suite.rc\" is deprecated in favour of \"flow.cylc\". Symlink created." "${REINSTALL_LOG}"
popd || exit 1
purge_rnd_suite

# Test cylc reinstall from within rundir, no args given
TEST_NAME="${TEST_NAME_BASE}-no-args"
make_rnd_suite
run_ok "${TEST_NAME}-install" cylc install --flow-name="${RND_SUITE_NAME}" -C "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}-install.stdout" <<__OUT__
INSTALLED ${RND_SUITE_NAME} from ${RND_SUITE_SOURCE} -> ${RUN_DIR}/${RND_SUITE_NAME}/run1
__OUT__
pushd "${RND_SUITE_RUNDIR}/run1" || exit 1
touch "${RND_SUITE_SOURCE}/new_file"
run_ok "${TEST_NAME}-reinstall" cylc reinstall
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/run1/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_SUITE_NAME}/run1 from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1" "${REINSTALL_LOG}"
exists_ok new_file
popd || exit 1
purge_rnd_suite

# Test cylc reinstall from within rundir, no args given
TEST_NAME="${TEST_NAME_BASE}-no-args-no-run-name"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
run_ok "${TEST_NAME}-install" cylc install --no-run-name -C "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}-install.stdout" <<__OUT__
INSTALLED ${RND_SUITE_NAME} from ${RND_SUITE_SOURCE} -> ${RUN_DIR}/${RND_SUITE_NAME}
__OUT__
pushd "${RND_SUITE_RUNDIR}" || exit 1
touch "${RND_SUITE_SOURCE}/new_file"
run_ok "${TEST_NAME}-reinstall" cylc reinstall
REINSTALL_LOG="$(find "${RND_SUITE_RUNDIR}/log/install" -type f -name '*reinstall.log')"
grep_ok "REINSTALLED ${RND_SUITE_NAME} from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}" "${REINSTALL_LOG}"
exists_ok new_file
popd || exit 1
popd || exit 1
purge_rnd_suite

exit
