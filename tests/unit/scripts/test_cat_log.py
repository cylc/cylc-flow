# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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

from cylc.flow.option_parsers import Options
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.scripts.cat_log import (
    colorise_cat_log,
    TAIL,
    TAIL_END,
    _main as cat_log,
    _get_remote_log,
    get_option_parser as cat_log_gop,
    get_tailer_template,
    view_log,
)


TAILER_PLATFORM = {
    'tail command template': 'tail -n +1 --follow=name %(filename)s',
    'tail from end command template':
    'tail -n %(lines)s --follow=name %(filename)s',
}


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


class TestGetTailerTemplate:
    """Tests for the get_tailer_template function."""

    @pytest.mark.parametrize(
        'mode, expected',
        [
            (TAIL, 'tail -n +1 --follow=name %(filename)s'),
            (TAIL_END, 'tail -n %(lines)s --follow=name %(filename)s'),
            ('unknown_mode', 'tail -n +1 --follow=name %(filename)s'),
        ],
    )
    def test_modes(self, mode, expected):
        """Test the tailer template selection for all supported modes."""
        result = get_tailer_template(TAILER_PLATFORM, mode)
        assert result == expected


async def test_get_remote_log_adds_tail_lines_for_tail_end(monkeypatch):
    """TAIL_END should pass --tail-lines to the remote cat-log command."""
    captured = {}

    async def mock_remote_cylc_cmd(cmd, platform, **kwargs):
        captured['cmd'] = cmd
        captured['kwargs'] = kwargs
        return 0

    monkeypatch.setattr(
        'cylc.flow.scripts.cat_log.remote_cylc_cmd',
        mock_remote_cylc_cmd
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.cat_log.get_remote_workflow_run_job_dir',
        lambda *a, **k: '/remote/workflow/log/job.out',
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.cat_log.verbosity_to_opts',
        lambda *a, **k: []
    )

    workflow_id = 'workflow'

    await _get_remote_log(
        workflow_id,
        TAILER_PLATFORM,
        point='1',
        task='foo',
        submit_num='NN',
        filename='job.out',
        mode=TAIL_END,
        tail_lines=42,
    )

    assert '--tail-lines=42' in captured['cmd']
    assert captured['kwargs']['manage'] is True


async def test_view_log_tail_vs_tail_end(tmp_path, capfd):
    """TAIL reads from the start; TAIL_END reads from the end."""
    logpath = tmp_path / 'job.out'
    lines = [
        'line-1',
        'line-2',
        'line-3',
        'line-4',
    ]
    logpath.write_text('\n'.join(lines) + '\n')

    await view_log(
        logpath,
        TAIL,
        'tail -n +1 %(filename)s',
    )
    out = capfd.readouterr().out.splitlines()
    assert out == lines

    await view_log(
        logpath,
        TAIL_END,
        'tail -n %(lines)s %(filename)s',
        tail_lines=2,
    )
    out = capfd.readouterr().out.splitlines()
    assert out == lines[-2:]

    await view_log(
        logpath,
        TAIL,
        'tail -n +1 --follow=name %(filename)s',
        batchview_cmd=f'cat {logpath}',
    )
    out = capfd.readouterr().out.splitlines()
    assert out == lines


async def test_bad_submit_number(monkeypatch, capsys):
    """Illegal submit numbers should be rejected before log lookup."""
    parser = cat_log_gop()

    async def mock_parse_id_async(*args, **kwargs):
        return 'workflow', {'task': 'foo', 'cycle': '1'}, None

    monkeypatch.setattr(
        'cylc.flow.scripts.cat_log.parse_id_async',
        mock_parse_id_async,
    )

    with pytest.raises(SystemExit):
        await cat_log(
            parser,
            Options(parser)(submit_num='not-a-number'),
            'workflow//1/foo',
        )
    assert 'Illegal submit number: not-a-number' in capsys.readouterr().err
