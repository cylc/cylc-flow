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

from cylc.flow.parsec.exceptions import IllegalItemError
import pytest
from cylc.flow.parsec.exceptions import Jinja2Error


async def test_validate_against_source_checks_source(
    capsys, validate, workflow_source, install, one_conf
):
    """Validation fails if validating against source with broken config.
    """
    src_dir = workflow_source(one_conf)
    workflow_id = install(src_dir)

    # Check that the original installation validates OK:
    validate(workflow_id, against_source=True)

    # Break the source config:
    with open(src_dir / 'flow.cylc', 'a') as handle:
        handle.write('\n[runtime]\n[[foo]]\nAgrajag = bowl of petunias')

    # # Check that Validate now fails:
    with pytest.raises(IllegalItemError, match='Agrajag'):
        validate(workflow_id, against_source=True)


async def test_validate_against_source_gets_old_tvars(
    workflow_source, capsys, validate, scheduler, run, install, run_dir
):
    """Validation will retrieve template variables from a previously played
    workflow.
    """
    src_dir = workflow_source({
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

    wf_id = install(src_dir)
    installed_dir = run_dir / wf_id

    # Check that the original installation validates OK:
    validate(installed_dir)

    # # Start a scheduler with tvars option:
    schd = scheduler(
        wf_id,
        templatevars=['FOO="foo"']
    )
    async with run(schd):
        pass

    # Replace foo in graph with {{FOO}} and check that this still
    # Validates (using db value for FOO):
    flow_file = (installed_dir / 'flow.cylc')
    flow_file.write_text(
        flow_file.read_text().replace('P1Y = foo', 'P1Y = {{FOO}}'))
    validate(wf_id, against_source=True)

    # Check that the source will not validate alone:
    flow_file = (src_dir / 'flow.cylc')
    flow_file.write_text(
        flow_file.read_text().replace('P1Y = foo', 'P1Y = {{FOO}}'))
    with pytest.raises(Jinja2Error):
        validate(src_dir)
