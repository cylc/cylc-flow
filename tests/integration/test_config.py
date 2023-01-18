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

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.parsec.exceptions import ListValueError


@pytest.mark.parametrize(
    'task_name,valid', [
        # valid task names
        ('a', True),
        ('a-b', True),
        ('a_b', True),
        ('foo', True),
        ('0aA-+%', True),
        # invalid task names
        ('a b', False),
        ('a£b', False),
        ('+ab', False),
        ('@ab', False),  # not valid in [runtime]
        ('_cylc', False),
        ('_cylcy', False),
    ]
)
def test_validate_task_name(
    flow,
    one_conf,
    validate,
    task_name: str,
    valid: bool
):
    """It should raise errors for invalid task names in the runtime section."""
    reg = flow({
        **one_conf,
        'runtime': {
            task_name: {}
        }
    })

    if valid:
        validate(reg)
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate(reg)
        assert task_name in str(exc_ctx.value)


@pytest.mark.parametrize(
    'task_name',
    [
        'root',
        '_cylc',
        '_cylcy',
    ]
)
def test_validate_implicit_task_name(
    flow,
    validate,
    task_name: str,
):
    """It should validate implicit task names in the graph.

    Note that most invalid task names get caught during graph parsing.
    Here we ensure that names which look like valid graph node names but which
    are blacklisted get caught and raise errors.
    """
    reg = flow({
        'scheduler': {
            'allow implicit tasks': 'True'
        },
        'scheduling': {
            'graph': {
                'R1': task_name
            }
        },
        'runtime': {
            # having one item in the runtime allows "root" to be expanded
            # which makes this test more thorough
            'whatever': {}
        }
    })

    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert str(exc_ctx.value).splitlines()[0] == (
        f'invalid task name "{task_name}"'
    )


@pytest.mark.parametrize(
    'env_var,valid', [
        ('foo', True),
        ('FOO', True),
        ('+foo', False),
    ]
)
def test_validate_env_vars(flow, one_conf, validate, env_var, valid):
    """It should validate environment variable names."""
    reg = flow({
        **one_conf,
        'runtime': {
            'foo': {
                'environment': {
                    env_var: 'value'
                }
            }
        }
    })
    if valid:
        validate(reg)
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate(reg)
        assert env_var in str(exc_ctx.value)


@pytest.mark.parametrize(
    'env_val', [
        '%(x)s',  # valid template but no such parameter x
        '%(a)123',  # invalid template
    ]
)
def test_validate_param_env_templ(
    flow,
    one_conf,
    validate,
    env_val,
    caplog,
    log_filter,
):
    """It should validate parameter environment templates."""
    reg = flow({
        **one_conf,
        'runtime': {
            'foo': {
                'environment': {
                    'foo': env_val
                }
            }
        }
    })
    validate(reg)
    assert log_filter(caplog, contains='bad parameter environment template')
    assert log_filter(caplog, contains=env_val)


def test_no_graph(flow, validate):
    """It should fail for missing graph sections."""
    reg = flow({
        'scheduling': {},
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert 'missing [scheduling][[graph]] section.' in str(exc_ctx.value)


def test_parameter_templates_setting(flow, one_conf, validate):
    """It should fail if [task parameter]templates is a setting.

    It should be a section.
    """
    reg = flow({
        **one_conf,
        'task parameters': {
            'templates': 'foo'
        }
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert '[templates] is a section' in str(exc_ctx.value)


@pytest.mark.parametrize(
    'section', [
        'external-trigger',
        'clock-trigger',
        'clock-expire',
    ]
)
def test_parse_special_tasks_invalid(flow, validate, section):
    """It should fail for invalid "special tasks"."""
    reg = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'initial cycle point': 'now',
            'special tasks': {
                section: 'foo (',  # missing closing bracket
            },
            'graph': {
                'R1': 'foo',
            },
        }
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert f'Illegal {section} spec' in str(exc_ctx.value)
    assert 'foo' in str(exc_ctx.value)


def test_parse_special_tasks_interval(flow, validate):
    """It should fail for invalid durations in clock-triggers."""
    reg = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'initial cycle point': 'now',
            'special tasks': {
                'clock-trigger': 'foo(PT1Y)',  # invalid ISO8601 duration
            },
            'graph': {
                'R1': 'foo'
            }
        }
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert 'Illegal clock-trigger spec' in str(exc_ctx.value)
    assert 'PT1Y' in str(exc_ctx.value)


@pytest.mark.parametrize(
    'section', [
        'external-trigger',
        'clock-trigger',
        'clock-expire',
    ]
)
def test_parse_special_tasks_families(flow, scheduler, validate, section):
    """It should expand families in special tasks."""
    reg = flow({
        'scheduling': {
            'initial cycle point': 'now',
            'special tasks': {
                section: 'FOO(P1D)',
            },
            'graph': {
                'R1': 'foo & foot',
            }
        },
        'runtime': {
            # family
            'FOO': {},
            # nested family
            'FOOT': {
                'inherit': 'FOO',
            },
            'foo': {
                'inherit': 'FOO',
            },
            'foot': {
                'inherit': 'FOOT',
            },
        }
    })
    if section == 'external-trigger':
        # external triggers cannot be used for multiple tasks so if family
        # expansion is completed correctly, validation should fail
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            config = validate(reg)
        assert 'external triggers must be used only once' in str(exc_ctx.value)
    else:
        config = validate(reg)
        assert set(config.cfg['scheduling']['special tasks'][section]) == {
            # the family FOO has been expanded to the tasks foo, foot
            'foo(P1D)',
            'foot(P1D)'
        }


def test_queue_treated_as_implicit(flow, validate):
    """Tasks listed in queue should be regarded as implicit

    https://github.com/cylc/cylc-flow/issues/5260
    """
    reg = flow(
        {
            "scheduling": {
                "queues": {"my_queue": {"members": "task1, task2"}},
                "graph": {"R1": "task2"},
            },
            "runtime": {"task2": {}},
        }
    )
    with pytest.raises(WorkflowConfigError, match="implicit tasks detected"):
        validate(reg)


def test_queue_treated_as_comma_separated(flow, validate):
    """Tasks listed in queue should be separated with commas, not spaces.

    https://github.com/cylc/cylc-flow/issues/5260
    """
    reg = flow(
        {
            "scheduling": {
                "queues": {"my_queue": {"members": "task1 task2"}},
                "graph": {"R1": "task2"},
            },
            "runtime": {"task1": {}, "task2": {}},
        }
    )
    with pytest.raises(ListValueError, match="cannot contain a space"):
        validate(reg)
