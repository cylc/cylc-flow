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

from pathlib import Path
import sqlite3
from typing import Any
import pytest

from cylc.flow.exceptions import (
    ServiceFileError,
    WorkflowConfigError,
    XtriggerConfigError,
)
from cylc.flow.parsec.exceptions import ListValueError
from cylc.flow.pathutil import get_workflow_run_pub_db_path

Fixture = Any


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
    id_ = flow({
        **one_conf,
        'runtime': {
            task_name: {}
        }
    })

    if valid:
        validate(id_)
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate(id_)
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
    id_ = flow({
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
        validate(id_)
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
    id_ = flow({
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
        validate(id_)
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate(id_)
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
    id_ = flow({
        **one_conf,
        'runtime': {
            'foo': {
                'environment': {
                    'foo': env_val
                }
            }
        }
    })
    validate(id_)
    assert log_filter(caplog, contains='bad parameter environment template')
    assert log_filter(caplog, contains=env_val)


def test_no_graph(flow, validate):
    """It should fail for missing graph sections."""
    id_ = flow({
        'scheduling': {},
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert 'missing [scheduling][[graph]] section.' in str(exc_ctx.value)


@pytest.mark.parametrize(
    'section', [
        'external-trigger',
        'clock-trigger',
        'clock-expire',
    ]
)
def test_parse_special_tasks_invalid(flow, validate, section):
    """It should fail for invalid "special tasks"."""
    id_ = flow({
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
        validate(id_)
    assert f'Illegal {section} spec' in str(exc_ctx.value)
    assert 'foo' in str(exc_ctx.value)


def test_parse_special_tasks_interval(flow, validate):
    """It should fail for invalid durations in clock-triggers."""
    id_ = flow({
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
        validate(id_)
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
    id_ = flow({
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
            config = validate(id_)
        assert 'external triggers must be used only once' in str(exc_ctx.value)
    else:
        config = validate(id_)
        assert set(config.cfg['scheduling']['special tasks'][section]) == {
            # the family FOO has been expanded to the tasks foo, foot
            'foo(P1D)',
            'foot(P1D)'
        }


def test_queue_treated_as_implicit(flow, validate, caplog):
    """Tasks in queues but not in runtime generate a warning.

    https://github.com/cylc/cylc-flow/issues/5260
    """
    id_ = flow(
        {
            "scheduling": {
                "queues": {"my_queue": {"members": "task1, task2"}},
                "graph": {"R1": "task2"},
            },
            "runtime": {"task2": {}},
        }
    )
    validate(id_)
    assert (
        'Queues contain tasks not defined in runtime'
        in caplog.records[0].message
    )


def test_queue_treated_as_comma_separated(flow, validate):
    """Tasks listed in queue should be separated with commas, not spaces.

    https://github.com/cylc/cylc-flow/issues/5260
    """
    id_ = flow(
        {
            "scheduling": {
                "queues": {"my_queue": {"members": "task1 task2"}},
                "graph": {"R1": "task2"},
            },
            "runtime": {"task1": {}, "task2": {}},
        }
    )
    with pytest.raises(ListValueError, match="cannot contain a space"):
        validate(id_)


def test_validate_incompatible_db(one_conf, flow, validate):
    """Validation should fail for an incompatible DB due to not being able
    to load template vars."""
    wid = flow(one_conf)
    # Create fake outdated DB
    db_file = Path(get_workflow_run_pub_db_path(wid))
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.touch()
    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            'CREATE TABLE suite_params(key TEXT, value TEXT, PRIMARY KEY(key))'
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(
        ServiceFileError, match="Workflow database is incompatible"
    ):
        validate(wid)

    # No tables should have been created
    stmt = "SELECT name FROM sqlite_master WHERE type='table'"
    conn = sqlite3.connect(db_file)
    try:
        tables = [i[0] for i in conn.execute(stmt)]
    finally:
        conn.close()
    assert tables == ['suite_params']


def test_xtrig_validation_wall_clock(
    flow: 'Fixture',
    validate: 'Fixture',
):
    """If an xtrigger module has a `validate()` function is called.

    https://github.com/cylc/cylc-flow/issues/5448
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'initial cycle point': '1012',
            'xtriggers': {'myxt': 'wall_clock(offset=PT755MH)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        WorkflowConfigError,
        match=r'Invalid offset: wall_clock\(offset=PT755MH\)'
    ):
        validate(id_)


def test_xtrig_validation_echo(
    flow: 'Fixture',
    validate: 'Fixture',
):
    """If an xtrigger module has a `validate()` function is called.

    https://github.com/cylc/cylc-flow/issues/5448
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'xtriggers': {'myxt': 'echo()'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        WorkflowConfigError,
        match=r'Requires \'succeed=True/False\' arg: echo()'
    ):
        validate(id_)


def test_xtrig_validation_xrandom(
    flow: 'Fixture',
    validate: 'Fixture',
):
    """If an xtrigger module has a `validate()` function it is called.

    https://github.com/cylc/cylc-flow/issues/5448
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'xtriggers': {'myxt': 'xrandom(200)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        WorkflowConfigError,
        match=r"'percent' should be a float between 0 and 100:"
    ):
        validate(id_)


def test_xtrig_validation_custom(
    flow: 'Fixture',
    validate: 'Fixture',
    monkeypatch: 'Fixture',
):
    """If an xtrigger module has a `validate()` function
    an exception is raised if that validate function fails.

    https://github.com/cylc/cylc-flow/issues/5448
    """
    # Rather than create our own xtrigger module on disk
    # and attempt to trigger a validation failure we
    # mock our own exception, xtrigger and xtrigger
    # validation functions and inject these into the
    # appropriate locations:
    GreenExc = type('Green', (Exception,), {})

    def kustom_xt(feature):
        return True, {}

    def kustom_validate(args, kwargs, sig):
        raise GreenExc('This is only a test.')

    # Patch xtrigger func
    monkeypatch.setattr(
        'cylc.flow.xtrigger_mgr.get_xtrig_func',
        lambda *args: kustom_xt,
    )
    # Patch xtrigger's validate func
    monkeypatch.setattr(
        'cylc.flow.config.get_xtrig_func',
        lambda *args: kustom_validate if "validate" in args else ''
    )

    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'initial cycle point': '1012',
            'xtriggers': {'myxt': 'kustom_xt(feature=42)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })

    Path(id_)
    with pytest.raises(GreenExc, match=r'This is only a test.'):
        validate(id_)


def test_xtrig_signature_validation(
    flow: 'Fixture',
    validate: 'Fixture',
):
    """Test automatic xtrigger function signature validation."""
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'xtriggers': {'myxt': 'xrandom()'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        XtriggerConfigError,
        match=r"xrandom\(\): missing a required argument: 'percent'"
    ):
        validate(id_)
