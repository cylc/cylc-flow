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
# Test "cylc reinstall" handling of external (non source) files in the run dir.

. "$(dirname "$0")/test_header"
set_test_number 6

make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1

# 1. Should delete an external file.

# Install source files.
run_ok "install-normal" cylc install

# Install an "external" file.
EXT_FILE=$HOME/cylc-run/${RND_WORKFLOW_NAME}/run1/external
touch "${EXT_FILE}"

run_ok "reinstall-normal" cylc reinstall "${RND_WORKFLOW_NAME}"

exists_fail "${EXT_FILE}"

# 2. Unless it is listed in .cylcignore.
basename "${EXT_FILE}" > .cylcignore
run_ok "install-cylcignore" cylc install

EXT_FILE=$HOME/cylc-run/${RND_WORKFLOW_NAME}/run2/external
touch "${EXT_FILE}"

run_ok "reinstall-cylcignore" cylc reinstall "${RND_WORKFLOW_NAME}"
exists_ok "${EXT_FILE}"

purge_rnd_workflow
