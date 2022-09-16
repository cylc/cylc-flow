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

from subprocess import Popen, PIPE

from ansimarkup import parse as cparse
from colorama import Style
import pytest

from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.scripts.cat_log import (
    colorise_cat_log,
)


@pytest.fixture
def log_file(tmp_path):
    _log_file = tmp_path / 'log'
    with open(_log_file, 'w+') as fh:
        fh.write('DEBUG - 1\n')
        fh.write('INFO - 2\n')
        fh.write('WARNING - 3\n')
        fh.write('ERROR - 4\n')
        fh.write('CRITICAL - 5\n')
    return _log_file


def test_colorise_cat_log_plain(log_file):
    """It should not colourise logs when color=False."""
    # command for colorise_cat_log to colourise
    cat_proc = Popen(
        ['cat', str(log_file)],
        stdout=PIPE,
    )
    colorise_cat_log(cat_proc, color=False)
    assert cat_proc.communicate()[0].decode().splitlines() == [
        # there should not be any ansii color characters here
        'DEBUG - 1',
        'INFO - 2',
        'WARNING - 3',
        'ERROR - 4',
        'CRITICAL - 5',
    ]


def test_colorise_cat_log_colour(log_file):
    """It should colourise logs when color=True."""
    # command for colorise_cat_log to colourise
    cat_proc = Popen(
        ['cat', str(log_file)],
        stdout=PIPE,
    )
    out, err = colorise_cat_log(cat_proc, color=True, stdout=PIPE)

    # strip the line breaks (because tags can come before or after them)
    # strip the reset tags (because they might not be needed if redeclared)
    out = ''.join(
        line.replace(Style.RESET_ALL, '')
        for line in out.decode().splitlines()
    )

    col = CylcLogFormatter.COLORS
    assert out == (
        ''.join([
            # strip the reset tags
            cparse(line).replace(Style.RESET_ALL, '')
            for line in [
                col['DEBUG'].format('DEBUG - 1'),
                'INFO - 2',
                col['WARNING'].format('WARNING - 3'),
                col['ERROR'].format('ERROR - 4'),
                col['CRITICAL'].format('CRITICAL - 5'),
                ''
            ]
        ])
    )
