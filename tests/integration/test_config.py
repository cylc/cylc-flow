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

import logging
from pathlib import Path
import sqlite3
from textwrap import dedent
from typing import Any
import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.globalcfg import GlobalConfig
from cylc.flow.exceptions import (
    InputError,
    PointParsingError,
    ServiceFileError,
    WorkflowConfigError,
    XtriggerConfigError,
)
from cylc.flow.parsec.exceptions import ListValueError
from cylc.flow.parsec.fileparse import read_and_proc
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
    assert log_filter(contains='bad parameter environment template')
    assert log_filter(contains=env_val)


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


def test_queue_treated_as_implicit(flow, validate, caplog, log_filter):
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
    assert log_filter(contains='Queues contain tasks not defined in runtime')


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
        'scheduling': {
            'initial cycle point': '1012',
            'xtriggers': {'myxt': 'wall_clock(offset=PT7MH)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(WorkflowConfigError, match=(
        r'\[@myxt\] wall_clock\(offset=PT7MH\)\n'
        r'Invalid offset: PT7MH'
    )):
        validate(id_)


def test_xtrig_implicit_wall_clock(flow: Fixture, validate: Fixture):
    """Test @wall_clock is allowed in graph without explicit
    xtrigger definition.
    """
    wid = flow({
        'scheduling': {
            'initial cycle point': '2024',
            'graph': {'R1': '@wall_clock => foo'},
        }
    })
    validate(wid)


def test_xtrig_validation_echo(
    flow: 'Fixture',
    validate: 'Fixture',
):
    """If an xtrigger module has a `validate()` function is called.

    https://github.com/cylc/cylc-flow/issues/5448
    """
    id_ = flow({
        'scheduling': {
            'xtriggers': {'myxt': 'echo()'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        WorkflowConfigError,
        match=r'Requires \'succeed=True/False\' arg'
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
        'scheduling': {
            'xtriggers': {'myxt': 'xrandom(200)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(
        XtriggerConfigError,
        match=r"'percent' should be a float between 0 and 100"
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
    def kustom_xt(feature):
        return True, {}

    def kustom_validate(args):
        raise Exception('This is only a test.')

    # Patch xtrigger func & its validate func
    monkeypatch.setattr(
        'cylc.flow.xtrigger_mgr.get_xtrig_func',
        lambda *args: kustom_validate if "validate" in args else kustom_xt
    )

    id_ = flow({
        'scheduling': {
            'initial cycle point': '1012',
            'xtriggers': {'myxt': 'kustom_xt(feature=42)'},
            'graph': {'R1': '@myxt => foo'},
        }
    })

    Path(id_)
    with pytest.raises(XtriggerConfigError, match=r'This is only a test.'):
        validate(id_)


@pytest.mark.parametrize('xtrig_call, expected_msg', [
    pytest.param(
        'xrandom()',
        r"missing a required argument: 'percent'",
        id="missing-arg"
    ),
    pytest.param(
        'wall_clock(alan_grant=1)',
        r"unexpected keyword argument 'alan_grant'",
        id="unexpected-arg"
    ),
])
def test_xtrig_signature_validation(
    flow: 'Fixture', validate: 'Fixture',
    xtrig_call: str, expected_msg: str
):
    """Test automatic xtrigger function signature validation."""
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2024',
            'xtriggers': {'myxt': xtrig_call},
            'graph': {'R1': '@myxt => foo'},
        }
    })
    with pytest.raises(XtriggerConfigError, match=expected_msg):
        validate(id_)


def test_special_task_non_word_names(flow: Fixture, validate: Fixture):
    """Test validation of special tasks names with non-word characters"""
    wid = flow({
        'scheduling': {
            'initial cycle point': '2020',
            'special tasks': {
                'clock-trigger': 't-1, t+1, t%1, t@1',
            },
            'graph': {
                'P1D': 't-1 & t+1 & t%1 & t@1',
            },
        },
        'runtime': {
            't-1, t+1, t%1, t@1': {'script': True},
        },
    })
    validate(wid)


async def test_glbl_cfg(monkeypatch, tmp_path, caplog):
    """Test accessing the global config via the glbl_cfg wrapper.

    Test the "cached" and "reload" kwargs to glbl_cfg.

    Also assert that accessing the global config during a reload operation does
    not cause issues. See https://github.com/cylc/cylc-flow/issues/6244
    """
    # wipe any previously cached config
    monkeypatch.setattr(
        'cylc.flow.cfgspec.globalcfg.GlobalConfig._DEFAULT', None
    )
    # load the global config from the test tmp directory
    monkeypatch.setenv('CYLC_CONF_PATH', str(tmp_path))

    def write_global_config(cfg_str):
        """Write the global.cylc file."""
        Path(tmp_path, 'global.cylc').write_text(cfg_str)

    def get_platforms(cfg_obj):
        """Return the platforms defined in the provided config instance."""
        return set(cfg_obj.get(['platforms']).keys())

    def expect_platforms_during_reload(platforms):
        """Test the platforms defined in glbl_cfg() during reload.

        Assert that the platforms defined in glbl_cfg() match the expected
        value, whilst the global config is in the process of being reloaded.

        In other words, this tests that the cached instance is not changed
        until after the reload has completed.

        See https://github.com/cylc/cylc-flow/issues/6244
        """
        caplog.set_level(logging.INFO)

        def _capture(fcn):
            def _inner(*args, **kwargs):
                cfg = glbl_cfg()
                assert get_platforms(cfg) == platforms
                logging.getLogger('test').info(
                    'ran expect_platforms_during_reload test'
                )
                return fcn(*args, **kwargs)
            return _inner

        monkeypatch.setattr(
            'cylc.flow.cfgspec.globalcfg.GlobalConfig._load',
            _capture(GlobalConfig._load)
        )

    # write a global config
    write_global_config('''
        [platforms]
            [[foo]]
    ''')

    # test the platforms defined in it
    assert get_platforms(glbl_cfg()) == {'localhost', 'foo'}

    # add a new platform the config
    write_global_config('''
        [platforms]
            [[foo]]
            [[bar]]
    ''')

    # the new platform should not appear (due to the cached instance)
    assert get_platforms(glbl_cfg()) == {'localhost', 'foo'}

    # if we request an uncached instance, the new platform should appear
    assert get_platforms(glbl_cfg(cached=False)) == {'localhost', 'foo', 'bar'}

    # however, this should not affect the cached instance
    assert get_platforms(glbl_cfg()) == {'localhost', 'foo'}

    # * if we reload the cached instance, the new platform should appear
    # * but during the reload itself, the old config should persist
    #   see https://github.com/cylc/cylc-flow/issues/6244
    expect_platforms_during_reload({'localhost', 'foo'})
    assert get_platforms(glbl_cfg(reload=True)) == {'localhost', 'foo', 'bar'}
    assert 'ran expect_platforms_during_reload test' in caplog.messages

    # the cache should have been updated by the reload
    assert get_platforms(glbl_cfg()) == {'localhost', 'foo', 'bar'}


def test_nonlive_mode_validation(flow, validate, caplog, log_filter):
    """Nonlive tasks return a warning at validation.
    """
    caplog.set_level(logging.INFO)
    msg1 = dedent(
        'The following tasks are set to run in skip mode:\n    * skip'
    )

    wid = flow({
        'scheduling': {
            'graph': {
                'R1': 'live => skip => simulation => dummy => default'
            }
        },
        'runtime': {
            'default': {},
            'live': {'run mode': 'live'},
            'skip': {
                'run mode': 'skip',
                'skip': {'outputs': 'started, submitted'}
            },
        },
    })

    validate(wid)
    assert log_filter(contains=msg1)


def test_skip_forbidden_as_output(flow, validate):
    """Run mode names are forbidden as task output names."""
    wid = flow({
        'scheduling': {'graph': {'R1': 'task'}},
        'runtime': {'task': {'outputs': {'skip': 'message for skip'}}}
    })
    with pytest.raises(
        WorkflowConfigError, match='Invalid task output .* cannot be: `skip`'
    ):
        validate(wid)


def test_validate_workflow_run_mode(
    flow: Fixture, validate: Fixture, caplog: Fixture
):
    """Test that Cylc validate will only check simulation mode settings
    if validate --mode simulation or dummy.
    Discovered in:
    https://github.com/cylc/cylc-flow/pull/6213#issuecomment-2225365825
    """
    wid = flow(
        {
            'scheduling': {'graph': {'R1': 'mytask'}},
            'runtime': {
                'mytask': {
                    'simulation': {'fail cycle points': 'invalid'},
                }
            },
        }
    )

    validate(wid)

    # It fails with run mode simulation:
    with pytest.raises(PointParsingError, match='Incompatible value'):
        validate(wid, run_mode='simulation')

    # It fails with run mode dummy:
    with pytest.raises(PointParsingError, match='Incompatible value'):
        validate(wid, run_mode='dummy')


async def test_invalid_starttask(one_conf, flow, scheduler, start):
    """It should reject invalid starttask arguments."""
    id_ = flow(one_conf)
    schd = scheduler(id_, starttask=['a///b'])
    with pytest.raises(InputError, match='a///b'):
        async with start(schd):
            pass


async def test_CYLC_WORKFLOW_SRC_DIR_correctly_set(tmp_path, install, run_dir):
    """CYLC_WORKFLOW_SRC_DIR is set correctly:

    * In source dir
    * In installed dir (Not testing different permutations of installed
      dir as these are covered by testing of `get_workflow_source_dir`)
    * Created directly in the run dir.

    """
    def process_file(target):
        """Run config through read_and_proc (~= cylc view --process)
        """
        return read_and_proc(
            target,
            viewcfg={
                'mark': False,
                'single': False,
                'label': False,
                'jinja2': True,
                'contin': True,
                'inline': True,
            },
        )

    # Setup a source directory:
    (tmp_path / 'flow.cylc').write_text(
        '#!jinja2\n{{ CYLC_WORKFLOW_SRC_DIR }}'
    )

    # Check that the CYLC_SRC_DIRECTORY
    # points to the source directory (tmp_path):
    processed = process_file(tmp_path / 'flow.cylc')
    assert processed[0] == str(tmp_path)

    # After installation the CYLC_WORKFLOW_SRC_DIR
    # *still* points back to tmp_path:
    wid = await install(tmp_path)
    processed = process_file(run_dir / wid / 'flow.cylc')
    assert processed[0] == str(tmp_path)
