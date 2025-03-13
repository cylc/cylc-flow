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
from types import SimpleNamespace
from tempfile import (
    NamedTemporaryFile,
    SpooledTemporaryFile,
    TemporaryFile,
    TemporaryDirectory,
)

import pytest

from cylc.flow import LOG
from cylc.flow.id import Tokens
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.task_events_mgr import TaskJobLogsRetrieveContext
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.subprocpool import (
    SubProcPool,
    _XTRIG_FUNC_CACHE,
    get_xtrig_func,
)
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_EXPIRED,
)
from cylc.flow.task_proxy import TaskProxy


def test_get_temporary_file():
    """Test SubProcPool.get_temporary_file."""
    assert isinstance(SubProcPool.get_temporary_file(), SpooledTemporaryFile)


def test_run_command_returns_0():
    """Test basic usage, command returns 0"""
    ctx = SubProcContext('truth', ['true'])
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == ''
    assert ctx.ret_code == 0


def test_run_command_returns_1():
    """Test basic usage, command returns 1"""
    ctx = SubProcContext('lies', ['false'])
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == ''
    assert ctx.ret_code == 1


def test_run_command_writes_to_out():
    """Test basic usage, command writes to STDOUT"""
    ctx = SubProcContext('parrot', ['echo', 'pirate', 'urrrr'])
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'pirate urrrr\n'
    assert ctx.ret_code == 0


def test_run_command_writes_to_err():
    """Test basic usage, command writes to STDERR"""
    ctx = SubProcContext(
        'parrot2',
        ['bash', '--noprofile', '--norc', '-c', 'echo pirate errrr >&2']
    )
    SubProcPool.run_command(ctx)
    assert 'pirate errrr\n'
    assert ctx.out == ''
    assert ctx.ret_code == 0


def test_run_command_with_stdin_from_str():
    """Test STDIN from string"""
    ctx = SubProcContext('meow', ['cat'], stdin_str='catches mice.\n')
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'catches mice.\n'
    assert ctx.ret_code == 0


def test_run_command_with_stdin_from_unicode():
    """Test STDIN from string with Unicode"""
    ctx = SubProcContext('meow', ['cat'], stdin_str='喵\n')
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == '喵\n'
    assert ctx.ret_code == 0


def test_run_command_with_stdin_from_handle():
    """Test STDIN from a single opened file handle"""
    handle = TemporaryFile()
    handle.write('catches mice.\n'.encode('UTF-8'))
    handle.seek(0)
    ctx = SubProcContext('meow', ['cat'], stdin_files=[handle])
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'catches mice.\n'
    assert ctx.ret_code == 0
    handle.close()


def test_run_command_with_stdin_from_path():
    """Test STDIN from a single file path"""
    handle = NamedTemporaryFile()
    handle.write('catches mice.\n'.encode('UTF-8'))
    handle.seek(0)
    ctx = SubProcContext('meow', ['cat'], stdin_files=[handle.name])
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'catches mice.\n'
    assert ctx.ret_code == 0
    handle.close()


def test_run_command_with_stdin_from_handles():
    """Test STDIN from multiple file handles"""
    handles = []
    for txt in ['catches mice.\n', 'eat fish.\n']:
        handle = TemporaryFile()
        handle.write(txt.encode('UTF-8'))
        handle.seek(0)
        handles.append(handle)
    ctx = SubProcContext('meow', ['cat'], stdin_files=handles)
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'catches mice.\neat fish.\n'
    assert ctx.ret_code == 0
    for handle in handles:
        handle.close()


def test_run_command_with_stdin_from_paths():
    """Test STDIN from multiple file paths"""
    handles = []
    for txt in ['catches mice.\n', 'eat fish.\n']:
        handle = NamedTemporaryFile()
        handle.write(txt.encode('UTF-8'))
        handle.seek(0)
        handles.append(handle)
    ctx = SubProcContext(
        'meow', ['cat'], stdin_files=[handle.name for handle in handles]
    )
    SubProcPool.run_command(ctx)
    assert ctx.err == ''
    assert ctx.out == 'catches mice.\neat fish.\n'
    assert ctx.ret_code == 0
    for handle in handles:
        handle.close()


def test_xfunction():
    """Test xtrigger function import."""
    with TemporaryDirectory() as temp_dir:
        python_dir = Path(temp_dir, "lib", "python")
        python_dir.mkdir(parents=True)
        the_answer_file = python_dir / "the_answer.py"
        with the_answer_file.open(mode="w") as f:
            f.write("""the_answer = lambda: 42""")
            f.flush()
            f_name = "the_answer"
        fn = get_xtrig_func(f_name, f_name, temp_dir)
        result = fn()
        assert 42 == result


def test_xfunction_cache():
    """Test xtrigger function import cache."""
    with TemporaryDirectory() as temp_dir:
        python_dir = Path(temp_dir, "lib", "python")
        python_dir.mkdir(parents=True)
        amandita_file = python_dir / "amandita.py"
        with amandita_file.open(mode="w") as f:
            f.write("""choco = lambda: 'chocolate'""")
            f.flush()
        m_name = "amandita"  # module
        f_name = "choco"  # function
        fn = get_xtrig_func(m_name, f_name, temp_dir)
        result = fn()
        assert 'chocolate' == result

        # is in the cache
        assert (m_name, f_name) in _XTRIG_FUNC_CACHE
        # returned from cache
        assert fn, get_xtrig_func(m_name, f_name == temp_dir)


def test_xfunction_import_error():
    """Test for error on importing a xtrigger function.

    To prevent the test eventually failing if the test function is added
    and successfully imported, we use an invalid module name as per Python
    spec.
    """
    with TemporaryDirectory() as temp_dir:
        with pytest.raises(ModuleNotFoundError):
            get_xtrig_func("invalid-module-name", "func-name", temp_dir)


def test_xfunction_attribute_error():
    """Test for error on looking for an attribute in a xtrigger script."""
    with TemporaryDirectory() as temp_dir:
        python_dir = Path(temp_dir, "lib", "python")
        python_dir.mkdir(parents=True)
        the_answer_file = python_dir / "the_sword.py"
        with the_answer_file.open(mode="w") as f:
            f.write("""the_droid = lambda: 'excalibur'""")
            f.flush()
        f_name = "the_sword"
        with pytest.raises(AttributeError):
            get_xtrig_func(f_name, f_name, temp_dir)


@pytest.fixture
def mock_ctx():
    def inner_(ret_code=None, host=None, cmd_key=None, cmd=None):
        """Provide a SimpleNamespace which looks like a ctx object."""
        inputs = locals()
        defaults = {
            'ret_code': 255,
            'host': 'mouse',
            'cmd_key': 'my-command',
            'cmd': ['bistromathic', 'take-off'],
        }
        for key in inputs:
            if inputs[key] is None:
                inputs[key] = defaults[key]
        ctx = SimpleNamespace(
            cmd=inputs['cmd'],
            timestamp=None,
            ret_code=inputs['ret_code'],
            host=inputs['host'],
            cmd_key=inputs['cmd_key'],
        )
        return ctx

    yield inner_


def _test_callback(ctx, foo=''):
    """Very Simple test callback function"""
    LOG.error(f'callback called.{foo}')


def _test_callback_255(ctx, foo=''):
    """Very Simple test callback function"""
    LOG.error(f'255 callback called.{foo}')


@pytest.mark.parametrize(
    'expect, ret_code, cmd_key',
    [
        pytest.param('callback called', 0, 'ssh something', id="return 0"),
        pytest.param('callback called', 1, 'ssh something', id="return 1"),
        pytest.param(
            'platform: None - Could not connect to mouse.',
            255,
            'ssh',
            id="return 255",
        ),
        pytest.param(
            'platform: localhost - Could not connect to mouse.',
            255,
            TaskJobLogsRetrieveContext(['ssh', 'something'], None, None),
            id="return 255 (log-ret)",
        ),
    ],
)
def test__run_command_exit(caplog, mock_ctx, expect, ret_code, cmd_key):
    """It runs a callback"""
    ctx = mock_ctx(ret_code=ret_code, cmd_key=cmd_key, cmd=['ssh'])
    SubProcPool._run_command_exit(
        ctx, callback=_test_callback, callback_255=_test_callback_255
    )
    assert expect in caplog.records[0].msg
    if ret_code == 255:
        assert '255 callback called.' in caplog.records[1].msg


def test__run_command_exit_no_255_callback(caplog, mock_ctx):
    """It runs the vanilla callback if no 255 callback provided"""
    SubProcPool._run_command_exit(mock_ctx(), callback=_test_callback)
    assert 'callback called' in caplog.records[0].msg


def test__run_command_exit_no_gettable_platform(caplog, mock_ctx):
    """It logs being unable to select a platform"""
    ret_ctx = TaskJobLogsRetrieveContext(
        platform_name='rhenas', max_size=256, key='rhenas'
    )
    ctx = mock_ctx(cmd_key=ret_ctx, cmd=['ssh'], ret_code=255)
    SubProcPool._run_command_exit(ctx, callback=_test_callback)
    assert 'platform: rhenas' in caplog.records[0].msg


def test__run_command_exit_no_255_args(caplog, mock_ctx):
    """It runs the 255 callback with the args of the callback if no
    callback 255 args provided.
    """
    SubProcPool._run_command_exit(
        mock_ctx(cmd=['ssh', 'Zaphod']),
        callback=_test_callback,
        callback_args=['Zaphod'],
        callback_255=_test_callback_255,
    )
    assert '255' in caplog.records[1].msg


def test__run_command_exit_add_to_badhosts(mock_ctx):
    """It updates the list of badhosts"""
    badhosts = {'foo', 'bar'}
    SubProcPool._run_command_exit(
        mock_ctx(cmd=['ssh']),
        bad_hosts=badhosts,
        callback=print,
        callback_args=['Welcome to Magrathea'],
    )
    assert badhosts == {'foo', 'bar', 'mouse'}


def test__run_command_exit_add_to_badhosts_log(caplog, mock_ctx):
    """It gets platform name from the callback args."""
    badhosts = {'foo', 'bar'}
    SubProcPool._run_command_exit(
        mock_ctx(cmd=['ssh']),
        bad_hosts=badhosts,
        callback=lambda x, t: print(str(x)),
        callback_args=[
            TaskProxy(
                Tokens('~u/w//c/t/2'),
                SimpleNamespace(
                    name='t',
                    dependencies={},
                    sequential='',
                    external_triggers=[],
                    xtrig_labels={},
                    expiration_offset=None,
                    outputs={
                        TASK_OUTPUT_SUBMITTED: [None, None],
                        TASK_OUTPUT_SUBMIT_FAILED: [None, None],
                        TASK_OUTPUT_SUCCEEDED: [None, None],
                        TASK_OUTPUT_FAILED: [None, None],
                        TASK_OUTPUT_EXPIRED: [None, None],
                    },
                    graph_children={},
                    rtconfig={'platform': 'foo'},
                ),
                ISO8601Point('1990'),
            )
        ],
    )
    assert 'platform: foo' in caplog.records[0].message
    assert badhosts == {'foo', 'bar', 'mouse'}


def test__run_command_exit_rsync_fails(mock_ctx):
    """It updates the list of badhosts"""
    badhosts = {'foo', 'bar'}
    ctx = mock_ctx(cmd=['rsync'], ret_code=42, cmd_key='file-install')
    SubProcPool._run_command_exit(
        ctx=ctx,
        bad_hosts=badhosts,
        callback=print,
        callback_args=[
            {
                'name': 'Magrathea',
                'ssh command': 'ssh',
                'rsync command': 'rsync command',
            },
            'Welcome to Magrathea',
        ],
    )
    assert badhosts == {'foo', 'bar', 'mouse'}


@pytest.mark.parametrize(
    'expect, ctx_kwargs',
    [
        (True, {'cmd': ['ssh'], 'ret_code': 255}),
        (False, {'cmd': ['foo'], 'ret_code': 255}),
        (False, {'cmd': ['ssh'], 'ret_code': 42}),
    ],
)
def test_ssh_255_fail(mock_ctx, expect, ctx_kwargs):
    """It knows when a ctx has failed"""
    output = SubProcPool.ssh_255_fail(mock_ctx(**ctx_kwargs))
    assert output == expect


@pytest.mark.parametrize(
    'expect, ctx_kwargs',
    [
        (True, {'cmd': ['rsync'], 'ret_code': 99, 'host': 'not_local'}),
        (True, {'cmd': ['rsync'], 'ret_code': 255, 'host': 'not_local'}),
        (False, {'cmd': ['make it-so'], 'ret_code': 255, 'host': 'not_local'}),
        (False, {'cmd': ['rsync'], 'ret_code': 125, 'host': 'localhost'}),
    ],
)
def test_rsync_255_fail(mock_ctx, expect, ctx_kwargs):
    """It knows when a ctx has failed"""
    output = SubProcPool.rsync_255_fail(
        mock_ctx(**ctx_kwargs),
        {'ssh command': 'ssh', 'rsync command': 'rsync command'},
    )
    assert output == expect
