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
# Test "cylc set-verbosity"
. "$(dirname "$0")/test_header"
set_test_number 3

KGO="/net/home/h02/tpilling/metomi/cylc-flow/tests/functional/cli/04-kgo/"

# List of sample scripts to test help documentation.
# broadcast - we want to keep this script consistent.
# message - we want to keep this script consistent. This script has two
#           valid arg groups.
# tui - slightly non-standard script.
SCRIPTS="broadcast message tui"

for script in $SCRIPTS; do
    # Generate KGO
    # cylc $script --help > $KGO/$script.help 2>&1
    cylc "$script" --help > "$script.help" 2>&1
    cmp_ok "$script.help" "$KGO/$script.help"
done
