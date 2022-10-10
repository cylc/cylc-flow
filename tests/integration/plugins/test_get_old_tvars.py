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

from cylc.flow.scheduler_cli import get_option_parser
from cylc.flow.parsec.exceptions import Jinja2Error
from cylc.flow.pre_configure.get_old_tvars import main as get_old_tvars
import pytest
from pytest import param
from types import SimpleNamespace

from cylc.flow.scripts.validate import (
    _main as validate,
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


@pytest.fixture(scope='module')
def create_workflow(mod_one_conf, mod_flow, mod_scheduler):
    # Set up opts and parser
    parser = get_option_parser()
    opts = SimpleNamespace(**parser.get_default_values().__dict__)
    opts.templatevars = ['FOO="From cylc template variables"']
    opts.templatevars_file = []

    conf = mod_one_conf
    # Set up scheduler
    schd = mod_scheduler(mod_flow(conf), templatevars=['FOO="bar"'])

    yield SimpleNamespace(schd=schd, opts=opts)


@pytest.mark.parametrize(
    'revalidate, expect',
    [
        (False, {}),
        (True, 'bar')
    ]
)
async def test_basic(create_workflow, mod_start, revalidate, expect):
    """It returns a pre-existing configuration if opts.revalidate is True"""
    opts = create_workflow.opts
    opts.revalidate = revalidate

    async with mod_start(create_workflow.schd):
        result = get_old_tvars(create_workflow.schd.workflow_run_dir, opts)
        if expect:
            assert result['template_variables']['FOO'] == expect
        else:
            assert result == expect


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
        param(config, config_gop, 'R1 = bar', id='config')
    )
)
@pytest.mark.parametrize(
    'revalidate',
    [
        (False),
        (True)
    ]
)
async def test_revalidate_validate(
    _setup, mod_start, capsys, function, parser, revalidate, expect,
):
    """It validates with Cylc Validate."""
    parser = parser()
    opts = SimpleNamespace(**parser.get_default_values().__dict__)
    opts.templatevars = []
    opts.templatevars_file = []
    opts.revalidate = revalidate
    if function == graph:
        opts.reference = True

    async with mod_start(_setup):
        if revalidate or expect == 'FOO':
            await function(parser, opts, _setup.workflow_name)
            assert expect in capsys.readouterr().out
        else:
            with pytest.raises(Jinja2Error, match="'FOO' is undefined"):
                await function(parser, opts, _setup.workflow_name)
