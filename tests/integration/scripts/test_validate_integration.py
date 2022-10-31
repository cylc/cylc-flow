#!/usr/bin/env python3

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

"""Integration tests for Cylc Validate CLI script."""

from cylc.flow.scripts.validate import wrapped_main as validate
from cylc.flow.parsec.exceptions import IllegalItemError
import pytest
from cylc.flow.parsec.exceptions import Jinja2Error


async def test_revalidate_checks_source(
    _source_workflow, capsys, _setup_validate_cli
):
    """Validation fails if revalidating with broken config.
    """
    wf = _source_workflow()

    setup = _setup_validate_cli({'against_source': True})

    # Check that the original installation validates OK:
    await validate(setup.parser, setup.opts, wf.opts.workflow_name)
    assert 'Valid for cylc-' in capsys.readouterr().out

    # Break the source config:
    with open(wf.src / 'flow.cylc', 'a') as handle:
        handle.write('\n[runtime]\n[[foo]]\nAgrajag = bowl of petunias')

    # Check that Validate now fails:
    with pytest.raises(IllegalItemError, match='Agrajag'):
        await validate(setup.parser, setup.opts, wf.opts.workflow_name)


async def test_revalidate_gets_old_tvars(
    _source_workflow, capsys, _setup_validate_cli, scheduler, run
):
    """Validation will retrieve template variables from a previously played
    workflow.
    """
    wf = _source_workflow({
        '#!jinja2': None,
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'initial cycle point': '1854',
            'graph': {
                'P1Y': 'foo'
            },
        },
        'runtime': {
            'foo': {
                'script': 'cylc pause ${CYLC_WORKFLOW_ID}'
            }
        }
    })

    setup = _setup_validate_cli({
        'revalidate': True,
    })

    # Check that the original installation validates OK:
    await validate(setup.parser, setup.opts, wf.opts.workflow_name)
    assert 'Valid for cylc-' in capsys.readouterr().out

    # Start a scheduler with tvars option:
    schd = scheduler(wf.opts.workflow_name, templatevars=['FOO="foo"'])
    async with run(schd):
        pass

    # Replace foo in graph with {{FOO}} and check that this still
    # Validates:
    wf.flow_file.write_text(
        wf.flow_file.read_text().replace('P1Y = foo', 'P1Y = {{FOO}}')
    )
    await validate(setup.parser, setup.opts, wf.opts.workflow_name)
    assert 'Valid for cylc-' in capsys.readouterr().out

    # Check that the source will not validate alone:
    setup.opts.revalidate = False
    with pytest.raises(Jinja2Error):
        await validate(setup.parser, setup.opts, str(wf.src))
