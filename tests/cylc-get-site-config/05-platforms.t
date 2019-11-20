#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

# Tests that Cylc can parse a variety of different job platforms.

. "$(dirname "$0")/test_header"
set_test_number 1

# ------------------------------------------------------------------------------
# Set up a global config user over-ride file with platform definitions in it.
create_test_globalrc '' ''

cat > etc/flow.rc <<'__HEREDOC__'
[job platforms]
    [[desktop\d\d|laptop\d\d]]
        # hosts = platform name (default)
        # Note: "desktop01" and "desktop02" are both valid and distinct platforms
    [[sugar]]
        hosts = localhost
        batch system = slurm
    [[hpc]]
        hosts = hpcl1, hpcl2
        retrieve job logs = True
        batch system = pbs
    [[hpcl1-bg]]
        hosts = hpcl1
        retrieve job logs = True
        batch system = background
    [[hpcl2-bg]]
        hosts = hpcl2
        retrieve job logs = True
        batch system = background
[platform aliases]
    [[hpc-bg]]
        platforms = hpcl1-bg, hpcl2-bg
__HEREDOC__

# ------------------------------------------------------------------------------
# Prints the flow.rc if the test has been made verbose
if [[ $TEST_VERBOSE == 1 ]]; then
    python3 -c """
from os import environ
conf_path = environ['CYLC_CONF_PATH']
w = 79
with open('etc/flow.rc', 'r') as handle:
    doc = handle.read()
print((f\"{'='*w}\n\"
       f\"CYLC_CONF_PATH is {conf_path}\n\"
       f\"The file at that location contains:\n\"
       f\"{'-'*79}\n{doc}\n{'='*79}\"
    )
)
    """ >&2
fi

# ------------------------------------------------------------------------------
# Check that cylc get-global-config can parse this.
TEST_NAME="${TEST_NAME_BASE}-validation"
run_ok ${TEST_NAME} cylc get-global-config
exit

# TODO Consider checking what happens if host is unset.
