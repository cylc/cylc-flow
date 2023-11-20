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
"""Integration test for the cat log script.
"""

import pytest

from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.cat_log import (
    _main as cat_log,
    get_option_parser as cat_log_gop
)


def test_fail_no_file(flow):
    """It produces a helpful error if there is no workflow log file.
    """
    parser = cat_log_gop()
    id_ = flow({})
    with pytest.raises(InputError, match='Log file not found.'):
        cat_log(parser, Options(parser)(), id_)


def test_fail_rotation_out_of_range(flow):
    """It produces a helpful error if rotation number > number of log files.
    """
    parser = cat_log_gop()
    id_ = flow({})
    path = flow.args[1]
    name = id_.split('/')[-1]
    logpath = (path / name / 'log/scheduler')
    logpath.mkdir(parents=True)
    (logpath / '01-start-01.log').touch()

    with pytest.raises(SystemExit):
        cat_log(parser, Options(parser)(rotation_num=0), id_)

    with pytest.raises(InputError, match='max rotation 0'):
        cat_log(parser, Options(parser)(rotation_num=1), id_)
