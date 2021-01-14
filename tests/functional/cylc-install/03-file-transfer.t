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
# Test rsync of workflow installation
. "$(dirname "$0")/test_header"
if ! command -v 'tree' >'/dev/null'; then
    skip_all '"tree" command not available'
fi
set_test_number 6

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
    rm -rf "${RND_SUITE_SOURCE}"
    rm -rf "${RND_SUITE_RUNDIR}"
}

# Test cylc install copies files to run dir successfully.
TEST_NAME="${TEST_NAME_BASE}-basic"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
mkdir .git .svn dir1 dir2 
touch .git/file1 .svn/file1 dir1/file1 dir2/file1 file1 file2
run_ok "${TEST_NAME}" cylc install "${RND_SUITE_NAME}" --no-run-name

tree -a -v -I '*.log|03-file-transfer*' "${RND_SUITE_RUNDIR}/" > 'basic-tree.out'
cmp_ok 'basic-tree.out'  <<__OUT__
${RND_SUITE_RUNDIR}/
├── .service
├── _cylc-install
│   └── source -> ${RND_SUITE_SOURCE}
├── dir1
│   └── file1
├── dir2
│   └── file1
├── file1
├── file2
├── flow.cylc
└── log
    └── install

7 directories, 5 files
__OUT__

contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}
__OUT__
popd || exit 1
purge_rnd_suite


# Test cylc install copies files to run dir successfully, exluding files from .cylcignore file.
TEST_NAME="${TEST_NAME_BASE}-cylcignore-file"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
mkdir .git .svn dir1 dir2 extradir1 extradir2
touch .git/file1 .svn/file1 dir1/file1 dir2/file1 extradir1/file1 extradir2/file1 file1 file2 .cylcignore
cat > .cylcignore <<__END__
dir*
extradir*
file2
__END__

run_ok "${TEST_NAME}" cylc install "${RND_SUITE_NAME}" --no-run-name

tree -a -v -I '*.log|03-file-transfer*' "${RND_SUITE_RUNDIR}/" > 'cylc-ignore-tree.out'
cmp_ok 'cylc-ignore-tree.out'  <<__OUT__
${RND_SUITE_RUNDIR}/
├── .service
├── _cylc-install
│   └── source -> ${RND_SUITE_SOURCE}
├── file1
├── flow.cylc
└── log
    └── install

5 directories, 2 files
__OUT__

contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}
__OUT__
popd || exit 1
purge_rnd_suite
