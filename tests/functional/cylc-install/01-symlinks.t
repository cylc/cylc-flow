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
# Test workflow installation symlinking localhost

. "$(dirname "$0")/test_header"

if [[ -z ${TMPDIR:-} || -z ${USER:-} || $TMPDIR/$USER == "$HOME" ]]; then
    skip_all '"TMPDIR" or "USER" not defined or "TMPDIR"/"USER" is "HOME"'
fi

set_test_number 14

create_test_global_config "" "
[symlink dirs]
    [[localhost]]
        run = \$TMPDIR/\$USER/test_cylc_symlink/cylctb_tmp_run_dir
        share = \$TMPDIR/\$USER/test_cylc_symlink/
        log = \$TMPDIR/\$USER/test_cylc_symlink/
        share/cycle = \$TMPDIR/\$USER/test_cylc_symlink/cylctb_tmp_share_dir
        work = \$TMPDIR/\$USER/test_cylc_symlink/
"

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

# Test "cylc install" ensure symlinks are created
TEST_NAME="${TEST_NAME_BASE}-symlinks-created"
make_rnd_suite
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_NAME}" --directory="${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__

TEST_SYM="${TEST_NAME_BASE}-run-symlink-exists-ok"

if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1") == \
    "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_run_dir/cylc-run/${RND_SUITE_NAME}/run1" ]]; then
        ok "$TEST_SYM"
else
    fail "$TEST_SYM"
fi



TEST_SYM="${TEST_NAME_BASE}-share/cycle-symlink-exists-ok"
if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1/share/cycle") == \
"$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_share_dir/cylc-run/${RND_SUITE_NAME}/run1/share/cycle" ]]; then
    ok "$TEST_SYM"
else
    fail "$TEST_SYM"
fi

for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME_BASE}-${DIR}-symlink-exists-ok"
    if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1/${DIR}") == \
   "$TMPDIR/${USER}/test_cylc_symlink/cylc-run/${RND_SUITE_NAME}/run1/${DIR}" ]]; then
        ok "$TEST_SYM"
    else
        fail "$TEST_SYM"
    fi
done
rm -rf "${TMPDIR}/${USER}/test_cylc_symlink/"
purge_rnd_suite



# Test "cylc install" --no-symlink-dirs
TEST_NAME="${TEST_NAME_BASE}-no-symlinks-created"
make_rnd_suite
run_ok "${TEST_NAME}" cylc install --flow-name="${RND_SUITE_NAME}" --no-symlink-dirs --directory="${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
INSTALLED $RND_SUITE_NAME from ${RND_SUITE_SOURCE} -> ${RND_SUITE_RUNDIR}/run1
__OUT__


TEST_SYM="${TEST_NAME_BASE}-run-symlink-exists-ok"

if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1") == \
    "$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_run_dir/cylc-run/${RND_SUITE_NAME}/run1" ]]; then
        fail "$TEST_SYM"
else
    ok "$TEST_SYM"
fi



TEST_SYM="${TEST_NAME_BASE}-share/cycle-symlink-not-exists-ok"
if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1/share/cycle") == \
"$TMPDIR/${USER}/test_cylc_symlink/cylctb_tmp_share_dir/cylc-run/${RND_SUITE_NAME}/share/cycle" ]]; then
    fail "$TEST_SYM"
else
    ok "$TEST_SYM"
fi

for DIR in 'work' 'share' 'log'; do
    TEST_SYM="${TEST_NAME_BASE}-${DIR}-symlink-not-exists-ok"
    if [[ $(readlink "$HOME/cylc-run/${RND_SUITE_NAME}/run1/${DIR}") == \
   "$TMPDIR/${USER}/test_cylc_symlink/cylc-run/${RND_SUITE_NAME}/${DIR}" ]]; then
        fail "$TEST_SYM"
    else
        ok "$TEST_SYM"
    fi
done
rm -rf "${TMPDIR}/${USER}/test_cylc_symlink/"
purge_rnd_suite
