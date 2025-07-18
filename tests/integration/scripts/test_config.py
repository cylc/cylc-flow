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

import json
import pytest

from cylc.flow.option_parsers import Options
from cylc.flow.scripts.config import _main, get_option_parser


@pytest.fixture(scope='module')
def setup(mod_one_conf, mod_flow):
    parser = get_option_parser()
    ConfigOptions = Options(parser)
    opts = ConfigOptions()
    opts.json = True
    wid = mod_flow(mod_one_conf)
    yield parser, opts, wid


async def test_json_basic(setup, capsys):
    """Test that the output is in JSON format."""
    await _main(*setup)

    result = capsys.readouterr()
    assert result.err == ''
    assert json.loads(result.out)['scheduling']['graph'] == {
        'R1': 'one'
    }


async def test_json_workflow_cfg(flow, capsys):
    """It fills in values from CLI."""
    wid = flow(
        {
            'scheduling': {'graph': {'P1D': 'foo'}},
            'runtime': {'foo': {}},
        }
    )
    parser = get_option_parser()
    ConfigOptions = Options(parser)
    opts = ConfigOptions()
    opts.json = True
    opts.icp = '    '

    await _main(parser, opts, wid)

    returned_config = json.loads(capsys.readouterr().out)
    assert returned_config['scheduling']['initial cycle point'] == '1000'
    assert returned_config['runtime']['foo'] == {
        'completion': 'succeeded',
        'simulation': {'default run length': 0.0}
    }


@pytest.mark.parametrize(
    'not_with',
    [
        (['print_platforms']),
        (['print_platforms', 'print_platform_names']),
        (['print_platforms', 'print_platform_names', 'print_hierarchy']),
    ],
)
async def test_json_and_not_other_option(
    setup, capsys, not_with
):
    """It fails if incompatible options provided."""
    parser, opts, wid = setup
    for key in not_with:
        setattr(opts, key, True)

    with pytest.raises(SystemExit):
        await _main(parser, opts, wid)

    result = capsys.readouterr()
    assert result.out == ''
    assert '--json incompatible with' in result.err
    for key in not_with:
        if 'platform' in key:
            key = key.strip('print_')
        assert key.replace('_', '-') in result.err

    # Clean up, since setup object is shared:
    for key in not_with:
        setattr(opts, key, False)


async def test_json_global_cfg(setup, mock_glbl_cfg, capsys):
    """It returns the global configuration in JSON format."""
    mock_glbl_cfg(
        'cylc.flow.scripts.config.glbl_cfg',
        '''
            [platforms]
                [[golders_green]]
                    [[[meta]]]
                        can = "Test lots of things"
                        because = metadata, is, not, fussy
                        number = 99
        ''',
    )
    parser, opts, _ = setup

    await _main(parser, opts)

    returned_config = json.loads(capsys.readouterr().out)
    assert returned_config == {
        'platforms': {
            'golders_green': {
                'meta': {
                    'can': 'Test lots of things',
                    'because': 'metadata, is, not, fussy',
                    'number': '99',
                }
            }
        }
    }


async def test_json_global_cfg_empty(setup, mock_glbl_cfg, capsys):
    """It returns an empty global configuration in JSON format."""
    parser, opts, _ = setup
    mock_glbl_cfg('cylc.flow.scripts.config.glbl_cfg', '')
    opts.item = ['scheduler][mail]']
    opts.json = True
    opts.defaults = True
    opts.none_str = 'zilch'

    await _main(parser, opts)

    returned_config = json.loads(capsys.readouterr().out)
    for key in ['footer', 'from', 'smtp', 'to']:
        assert returned_config[key] == 'zilch'
