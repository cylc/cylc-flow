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

import logging

import pytest

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.parsec.exceptions import IllegalItemError, Jinja2Error


async def test_validate_against_source_checks_source(
    capsys, validate, workflow_source, install, one_conf
):
    """Validation fails if validating against source with broken config.
    """
    src_dir = workflow_source(one_conf)
    workflow_id = await install(src_dir)

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

    wf_id = await install(src_dir)
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


def test_validate_simple_graph(flow, validate, caplog):
    """Test deprecation notice for Cylc 7 simple graph (no recurrence section)
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {'dependencies': {'graph': 'foo'}}
    })
    validate(id_)
    expect = (
        'graph items were automatically upgraded'
        ' in "workflow definition":'
        '\n * (8.0.0) [scheduling][dependencies]graph -> [scheduling][graph]R1'
    )
    assert expect in caplog.messages


def test_pre_cylc8(flow, validate, caplog):
    """Test all current non-silent workflow obsoletions and deprecations.
    """
    id_ = flow({
        'cylc': {
            'events': {
                'reset timer': 10,
                'reset inactivity timer': 15,
            }
        },
        "scheduling": {
            "initial cycle point": "20150808T00",
            "final cycle point": "20150808T00",
            "graph": {
                "P1D": "foo => cat & dog"
            },
            "special tasks": {
                "external-trigger": 'cat("meow available")'
            }
        },
        'runtime': {
            'foo, cat, dog': {
                'suite state polling': {'template': ''},
                'events': {'reset timer': 20}
            }
        }
    }, defaults=False)
    validate(id_)
    for warning in (
        (
            ' * (7.8.0) [runtime][foo, cat, dog][suite state polling]template'
            ' - DELETED (OBSOLETE)'),
        ' * (7.8.1) [cylc][events]reset timer - DELETED (OBSOLETE)',
        ' * (7.8.1) [cylc][events]reset inactivity timer - DELETED (OBSOLETE)',
        (
            ' * (7.8.1) [runtime][foo, cat, dog][events]reset timer'
            ' - DELETED (OBSOLETE)'),
        (
            ' * (8.0.0) [runtime][foo, cat, dog][suite state polling]'
            ' -> [runtime][foo, cat, dog][workflow state polling]'
            ' - value unchanged'),
        ' * (8.0.0) [cylc] -> [scheduler] - value unchanged'
    ):
        assert warning in caplog.messages


def test_graph_upgrade_msg_default(flow, validate, caplog):
    """It lists Cycling definitions which need upgrading."""
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'initial cycle point': 1042,
            'dependencies': {
                'R1': {'graph': 'foo'},
                'P1Y': {'graph': 'bar & baz'}
            }
        },
    })
    validate(id_)
    assert '[scheduling][dependencies][X]graph' in caplog.messages[0]
    assert 'for X in:\n       P1Y, R1' in caplog.messages[0]


def test_graph_upgrade_msg_graph_equals(flow, validate, caplog):
    """It gives a more useful message in special case where graph is
    key rather than section:

    [scheduling]
        [[dependencies]]
            graph = foo => bar
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {'dependencies': {'graph': 'foo => bar'}},
    })
    validate(id_)
    expect = ('[scheduling][dependencies]graph -> [scheduling][graph]R1')
    assert expect in caplog.messages[0]


def test_graph_upgrade_msg_graph_equals2(flow, validate, caplog):
    """Both an implicit R1 and explict reccurance exist:
    It appends a note.
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'initial cycle point': '1000',
            'dependencies': {
                'graph': 'foo => bar', 'P1Y': {'graph': 'a => b'}}},
    })
    validate(id_)
    expect = (
        'graph items were automatically upgraded in'
        ' "workflow definition":'
        '\n * (8.0.0) [scheduling][dependencies][X]graph'
        ' -> [scheduling][graph]X - for X in:'
        '\n       P1Y, graph'
        '\n   ([scheduling][dependencies]graph moves to [scheduling][graph]R1)'
    )
    assert expect in caplog.messages[0]


def test_undefined_parent(flow, validate):
    """It should catch tasks which inherit from implicit families."""
    id_ = flow({
        'scheduling': {'graph': {'R1': 'foo'}},
        'runtime': {'foo': {'inherit': 'FOO'}}
    })
    with pytest.raises(WorkflowConfigError, match='undefined parent for foo'):
        validate(id_)


def test_log_parent_demoted(flow, validate, monkeypatch, caplog, log_filter):
    """It should log family "demotion" in verbose mode."""
    monkeypatch.setattr(
        'cylc.flow.flags.verbosity',
        10,
    )
    caplog.set_level(logging.DEBUG)
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo'
            }
        },
        'runtime': {
            'foo': {'inherit': 'None, FOO'},
            'FOO': {},
        }
    })
    validate(id_)
    assert log_filter(caplog, contains='First parent(s) demoted to secondary')
    assert log_filter(caplog, contains="FOO as parent of 'foo'")
