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

import pytest
from pytest import param
from types import SimpleNamespace

from cylc.flow.scripts.validate import (
    wrapped_main as validate,
    get_option_parser as validate_gop
)
from cylc.flow.scripts.view import (
    _main as view,
    get_option_parser as view_gop
)
from cylc.flow.scripts.graph import (
    _main as graph,
    get_option_parser as graph_gop
)
from cylc.flow.scripts.config import (
    _main as config,
    get_option_parser as config_gop
)
from cylc.flow.scripts.list import (
    _main as cylclist,
    get_option_parser as list_gop
)


@pytest.fixture(scope='module')
def _setup(mod_scheduler, mod_flow):
    """Provide an installed flow with a database to try assorted
    simple Cylc scripts against.
    """
    conf = {
        '#!jinja2': '',
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': r'{{FOO}}'
            }
        }
    }
    schd = mod_scheduler(mod_flow(conf), templatevars=['FOO="bar"'])
    yield schd


@pytest.mark.parametrize(
    'function, parser, expect',
    (
        param(validate, validate_gop, 'Valid for', id="validate"),
        param(view, view_gop, 'FOO', id="view"),
        param(graph, graph_gop, '1/bar', id='graph'),
        param(config, config_gop, 'R1 = bar', id='config'),
        param(cylclist, list_gop, 'bar', id='list')
    )
)
async def test_revalidate_validate(
    _setup, mod_start, capsys, function, parser, expect,
):
    """It (A Cylc CLI Command) can get template vars stored in db.

    Else the jinja2 in the config would cause these tasks to fail.
    """
    from cylc.flow.option_parsers import Options
    parser = parser()
    opts = Options(parser)()
    if function == graph:
        opts.reference = True

    async with mod_start(_setup):
        if function == view:
            await function(opts, _setup.workflow_name)
        else:
            await function(parser, opts, _setup.workflow_name)
        assert expect in capsys.readouterr().out
