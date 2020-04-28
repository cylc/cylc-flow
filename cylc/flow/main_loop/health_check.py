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
"""Checks the integrity of the suite run directory.

* Ensures suite run directory is still present.
* Ensures contact file is present and consistent with the running suite.

Shuts down the suite in the enent of inconsistency or error.

"""
import os

from cylc.flow import suite_files
from cylc.flow.exceptions import CylcError, SuiteServiceFileError
from cylc.flow.main_loop import periodic


@periodic
async def health_check(scheduler, _):
    """Perform suite health checks."""
    # 1. check if suite run dir still present - if not shutdown.
    _check_suite_run_dir(scheduler)
    # 2. check if contact file consistent with current start - if not
    #    shutdown.
    _check_contact_file(scheduler)


def _check_suite_run_dir(scheduler):
    if not os.path.exists(scheduler.suite_run_dir):
        raise CylcError(
            'Suite run directory does not exist:'
            f' {scheduler.suite_run_dir}'
        )


def _check_contact_file(scheduler):
    try:
        contact_data = suite_files.load_contact_file(
            scheduler.suite)
        if contact_data != scheduler.contact_data:
            raise CylcError('contact file modified')
    except (AssertionError, IOError, ValueError, SuiteServiceFileError):
        raise CylcError(
            '%s: contact file corrupted/modified and may be left'
            % suite_files.get_contact_file(scheduler.suite)
        )
