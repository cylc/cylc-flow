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

"""Tests for the "cylc report-timings" command."""

import pytest

from cylc.flow.commands import force_trigger_tasks, run_cmd
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.report_timings import (
    FORMATS,
    _main,
    get_option_parser,
)


RTOptions = Options(get_option_parser())


@pytest.fixture(scope='module')
async def workflow(mod_flow, mod_scheduler, mod_run, mod_complete):
    """Simple workflow to test report-timings against.

    Uses real cycles which run in order to ensure averaging is performed over
    something "real".
    """
    id_ = mod_flow({
        'scheduling': {
            'initial cycle point': '1',
            'final cycle point': '3',
            'cycling mode': 'integer',
            'graph': {
                'P1': '''
                    a => b => c
                    b[-P1] => b
                '''
            },
        },
    })
    schd = mod_scheduler(id_, paused_start=False)
    async with mod_run(schd):
        await mod_complete(schd, '2/b')
        # re-run 1/b (activates _reshape_timings logic)
        await run_cmd(force_trigger_tasks(schd, ['1/b'], ['1']))
        await mod_complete(schd)
        yield schd


def test_raw(workflow, capsys):
    """Test --format=raw"""
    _main(RTOptions(format='raw'), workflow.tokens.id)
    out, err = capsys.readouterr()

    # nothing written to sterrr
    assert not err

    # something written to stdout
    lines = out.splitlines()
    assert len(lines) == 11  # (3 tasks x 3 cycles) + 1 re-run + 1 header row

    assert lines[1].split()[:4] == ['a', '1', 'simulation', 'simulation']


def test_summary(workflow, capsys):
    """Test --format=summary"""
    _main(RTOptions(format='summary'), workflow.tokens.id)
    out, err = capsys.readouterr()

    # nothing written to sterrr
    assert not err

    lines = out.splitlines()

    # the header
    assert 'Host: simulation' in lines[1]
    assert 'Job Runner: simulation' in lines[1]

    # the first data row
    assert lines[6].split() == [
        'a',
        '3.0',
        '0.0',
        '0.0',
        '0.0',
        '0.0',
        '0.0',
        '0.0',
        '0.0',
    ]


def test_html(workflow, capsys):
    """Test --format=html"""
    _main(RTOptions(format='html'), workflow.tokens.id)
    out, err = capsys.readouterr()

    # nothing written to sterrr
    assert not err

    # headings present
    assert '<h2>Queue Time</h2>' in out

    # plots present
    assert '<svg' in out

    # custom CSS injected
    assert 'background-color: #f0f0f0' in out


@pytest.mark.parametrize('format', list(FORMATS))
def test_output(workflow, capsys, tmp_path, format):
    """Test the --output-filename argument redirects output."""
    temp_file = tmp_path / 'file'
    _main(
        RTOptions(format=format, output_filename=str(temp_file)),
        workflow.tokens.id,
    )

    # nothing written to stdout/err
    out, err = capsys.readouterr()
    assert not err
    assert not out

    # something written to the specified file
    assert temp_file.exists()
    with open(temp_file, 'r') as output_file:
        assert len(output_file.read().splitlines()) > 3
