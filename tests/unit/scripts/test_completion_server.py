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

from types import SimpleNamespace

from cylc.flow.async_util import pipe
from cylc.flow.id import Tokens
from cylc.flow.network.scan import scan
from cylc.flow.scripts.completion_server import (
    _list_prereqs_and_outputs,
    server,
    complete_cylc,
    complete_command,
    complete_option,
    complete_option_value,
    complete_argument,
    list_cylc_id,
    list_options,
    list_option_values,
    list_workflows,
    list_src_workflows,
    list_in_workflow,
    list_resources,
    list_dir,
    list_flows,
    list_colours,
    cli_detokenise,
    get_completion_script_file,
    get_current_completion_script_version,
    check_completion_script_compatibility,
    COMMANDS,
)
from cylc.flow.scripts.trigger import get_option_parser

import pytest


def setify(coro):
    """Cast returned lists to sets for coroutines.

    Convenience function to use when you want to test output not order.
    """
    async def _coro(*args, **kwargs):
        nonlocal coro
        ret = await coro(*args, **kwargs)
        if isinstance(ret, list):
            return set(ret)
        return ret
    return _coro


@pytest.fixture
def dummy_workflow(tmp_path, monkeypatch, mock_glbl_cfg):
    """A simple workflow run dir with some job directories to inspect.

    This patches the relevant interfaces so that this workflow will show up
    e.g. in the scan interface.
    """
    install_dir = tmp_path / 'foo'
    install_dir.mkdir()
    (install_dir / 'run1').mkdir()
    run_dir = install_dir / 'run2'
    run_dir.mkdir()
    (install_dir / 'runN').symlink_to('run2', target_is_directory=True)
    (run_dir / 'flow.cylc').touch()
    job_log_dir = (run_dir / 'log') / 'job'
    job_log_dir.mkdir(parents=True)
    for cycle in ('1', '2', '3'):
        for task in ('foo', 'bar', 'baz'):
            for job in ('01', 'NN'):
                ((job_log_dir / cycle) / task / job).mkdir(parents=True)

    # patch scan for list_workflows
    @pipe
    async def _scan(*args, **kwargs):
        nonlocal tmp_path
        kwargs['run_dir'] = tmp_path
        async for flow in scan(*args, **kwargs):
            yield flow

    monkeypatch.setattr(
        'cylc.flow.scripts.scan.scan',
        _scan,
    )

    # patch scan for list_src_workflows
    mock_glbl_cfg(
        'cylc.flow.scripts.completion_server.glbl_cfg',
        f'''
            [install]
                source dirs = {tmp_path}
        '''
    )

    # patch get_workflow_run_job_dir for list_in_workflow
    monkeypatch.setattr(
        'cylc.flow.pathutil._CYLC_RUN_DIR',
        tmp_path,
    )


async def test_server():
    """Test the request/response server."""
    def _listener(timeout=None):
        """The listener yields requests."""
        yield 'cylc|trigger|'
        yield 'cylc|trigger|one|'

    async def _responder(*parts):
        """The responder computes responses."""
        return [f'x{part}' for part in parts]

    # in "once" mode the server shuts down after returning the first response
    ret = []
    await server(_listener, _responder, once=True, write=ret.append)
    assert ret == [
        'xcylc xtrigger'
    ]

    # otherwise the server stays up until the listener returns
    ret = []
    await server(_listener, _responder, once=False, write=ret.append)
    assert ret == [
        'xcylc xtrigger',
        'xcylc xone xtrigger',  # the server sorts the responses
    ]

    # if *anything* goes wrong the server should send an empty response
    # rather than crashing
    async def _responder(*parts):
        raise Exception()
    ret = []
    await server(_listener, _responder, once=True, write=ret.append)
    assert ret == ['']


async def test_complete_cylc(dummy_workflow):
    """Test the completion for everything Cylc.

    Each individual completion function is tested individually too. This test
    is to ensure they work together correctly.
    """
    _complete_cylc = setify(complete_cylc)  # results are un-ordered

    # $ cylc<tab><tab>
    assert 'trigger' in await _complete_cylc('cylc')
    assert 'help' in await _complete_cylc('cylc')

    # $ cylc tri<tab><tab>
    assert 'trigger' in await _complete_cylc('cylc', 'tri')

    # $ cylc trigger<tab><tab>
    assert await _complete_cylc('cylc', 'trigger') == {
        'trigger',
    }

    # $ cylc trigger <tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '') == {
        'foo/run2//',
    }

    # $ cylc triger f<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'f') == {
        'foo/run2//',
    }

    # $ cylc triger foo/run2//<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'foo/run2//') == {
        'foo/run2//1/',
        'foo/run2//2/',
        'foo/run2//3/',
    }

    # $ cylc triger foo/run2//1<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'foo/run2//1') == {
        'foo/run2//1/',
    }

    # $ cylc triger foo/run2//1/<tab><tab>
    assert set(await _complete_cylc('cylc', 'trigger', 'foo/run2//1/')) == {
        'foo/run2//1/foo/',
        'foo/run2//1/bar/',
        'foo/run2//1/baz/',
    }

    # $ cylc triger foo/run2//1/f<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'foo/run2//1/f') == {
        'foo/run2//1/foo/',
    }

    # $ cylc triger foo/run2//1/foo/<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'foo/run2//1/foo/') == {
        'foo/run2//1/foo/01/',
        'foo/run2//1/foo/NN/',
    }

    # $ cylc triger foo/run2//1/foo/N<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', 'foo/run2//1/foo/N') == {
        'foo/run2//1/foo/NN/',
    }

    # $ cylc triger -<tab><tab>
    assert '--flow' in await _complete_cylc('cylc', 'trigger', '-')

    # $ cylc triger --flow <tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '--flow', '') == {
        'all',
        'none',
        'new',
    }

    # $ cylc triger --flow <tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '--flow', 'all', '') == {
        'foo/run2//'
    }

    # $ cylc triger --flow=<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '--flow=') == {
        '--flow=all',
        '--flow=none',
        '--flow=new',
    }

    # $ cylc triger --flow=all <tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '--flow=all', '') == {
        'foo/run2//'
    }

    # $ cylc triger --62656566<tab><tab>
    assert await _complete_cylc('cylc', 'trigger', '--62656566') == set()

    # $ cylc triger 62656566 --77656C6C696E67746F6E<tab><tab>
    assert await _complete_cylc(
        'cylc', '62656566', '--77656C6C696E67746F6E='
    ) == set()

    # $ cylc cat-log f<tab><tab>
    assert await _complete_cylc('cylc', 'cat-log', 'f') == {'foo/run2//'}

    # $ cylc log f<tab><tab>  # NOTE: "log" is an alias for "cat-log"
    assert await _complete_cylc('cylc', 'log', 'f') == {'foo/run2//'}

    # $ cylc help <tab><tab>
    assert 'all' in await _complete_cylc('cylc', 'help', '')

    # $ cylc version <tab><tab>
    assert '--long' in await _complete_cylc('cylc', 'version', '')


async def test_complete_command():
    """Test completion for Cylc commands."""
    ret = await complete_command('t')
    assert 'tui' in ret
    assert 'trigger' in ret

    ret = await complete_command('tri')
    assert 'tui' not in ret
    assert 'trigger' in ret

    # we should get an empty list for a non-existent command
    ret = await complete_command('626565662077656C6C696E67746F6E')
    assert ret == []


async def test_complete_option():
    """Test completion for --options of Cylc commands."""
    ret = await complete_option('trigger')
    assert all(
        item.startswith('-')
        for item in ret
    )
    assert '--flow' in ret

    # we should get an empty list for a non-existent options
    ret = await complete_option('626565662077656C6C696E67746F6E')
    assert ret == []

    assert await complete_option('trigger', '--flow=a') == ['--flow=all']

    # we should get None for no existent options, this enables use to fail
    # over to other completion methods
    assert await complete_option('trigger', '--float=a') is None


async def test_option_value():
    """Test completion for values of --options of Cylc commands."""
    ret = await complete_option_value('trigger', '--flow')
    assert 'all' in ret
    assert 'none' in ret

    ret = await complete_option_value('trigger', '--flow', 'a')
    assert 'all' in ret
    assert 'none' not in ret

    # we should get None for no existent values, this enables use to fail
    # over to other completion methods
    ret = await complete_option_value('626565662077656C6C696E67746F6E', 'x')
    assert ret is None

    ret = await complete_option_value('trigger', '626565662077656C6C696E6774')
    assert ret is None


async def test_complete_argument(monkeypatch):
    """Test completions for positional arguments of Cylc commands."""
    # register two fake commands with their own special completions
    def _complete_arg(x):
        async def __complete_arg(*args):
            nonlocal x
            return x
        return __complete_arg

    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.COMMAND_MAP',
        {
            'foo': _complete_arg(['aaa', 'bbb']),
            'bar': _complete_arg(['ccc', 'ddd']),
            'baz': None,
        }
    )

    # patch the default ID listing completion
    async def _list_cylc_id(*args):
        return ['eee', 'fff']

    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.list_cylc_id',
        _list_cylc_id
    )

    # the foo command should provide foo-specific completions
    ret = await complete_argument('foo')
    assert ret == ['aaa', 'bbb']

    ret = await complete_argument('foo', 'a')
    assert ret == ['aaa']

    # the bar command should provide bar-specific completions
    ret = await complete_argument('bar')
    assert ret == ['ccc', 'ddd']

    # the bax command should not provide argument completions
    ret = await complete_argument('baz')
    assert ret == []

    # all other commands should fallback to the default completions
    ret = await complete_argument('pub')
    assert ret == ['eee', 'fff']


async def test_list_cylc_id(monkeypatch):
    """Test listing Cylc IDs.

    This test ensures that list_cylc_ids is calling the right interfaces.
    """
    _list_cylc_id = setify(list_cylc_id)

    async def _list_workflows():
        return ['abc', 'bcd', 'cde']

    async def _list_in_workflow(tokens):
        if tokens.workflow_id == 'abc':
            return ['1', '2']
        return ['2', '3']

    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.list_workflows',
        _list_workflows,
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.list_in_workflow',
        _list_in_workflow,
    )

    assert await _list_cylc_id(None) == {'abc', 'bcd', 'cde'}
    assert await _list_cylc_id('a') == {'abc', 'bcd', 'cde'}
    assert await _list_cylc_id('abc//') == {'1', '2'}
    assert await _list_cylc_id('bcd//') == {'2', '3'}


def test_list_options(monkeypatch):
    """Test listing of command --options."""
    assert '--flow' in list_options('trigger')
    assert '--color' in list_options('trigger')
    # we should get an empty list if anything goes wrong
    assert list_options('zz9+za') == []

    # patch the logic to turn off the auto_add behaviour of CylcOptionParser
    class EntryPoint:
        def load(self):
            def _parser_function():
                parser = get_option_parser()
                del parser.auto_add
                return parser
            return SimpleNamespace(parser_function=_parser_function)
    monkeypatch.setitem(
        COMMANDS,
        'trigger',
        EntryPoint(),
    )

    # with auto_add turned off the --color option should be absent
    assert '--color' not in list_options('trigger')


async def test_list_option_values(monkeypatch):
    """Test listing of --option values."""
    _list_option_values = setify(list_option_values)

    async def _list_a_options(*args):
        return ['foo', 'bar', 'baz']

    # register two options
    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.OPTION_MAP',
        {
            # --a has a registered completion
            '--a': _list_a_options,
            # --b has completions explicitly turned off
            '--b': None,
            # --c is not registered
        },
    )

    assert await _list_option_values(None, '--a', None) == {
        'foo',
        'bar',
        'baz'
    }
    assert await _list_option_values(None, '--b', None) == set()
    assert await _list_option_values(None, '--c', None) is None


async def test_list_workflows(dummy_workflow):
    """Test listing workflows (via "scan")."""
    # test list_workflows
    assert await list_workflows() == ['foo/run2//']
    assert await list_workflows(states={'running'}) == []

    # test list_src_workflows
    assert await list_src_workflows(None) == ['foo/run2']


async def test_list_in_workflow(dummy_workflow):
    """Test listing of "things" within workflows.

    Things i.e. cycles/tasks/jobs.
    """
    _list_in_workflow = setify(list_in_workflow)

    # workflow => list cycles
    assert await _list_in_workflow(Tokens('foo/run2//')) == {
        'foo/run2//1/',
        'foo/run2//2/',
        'foo/run2//3/',
    }
    # cycle => list tasks
    assert await _list_in_workflow(Tokens('foo/run2//1')) == {
        'foo/run2//1/foo/',
        'foo/run2//1/bar/',
        'foo/run2//1/baz/',
    }
    # task => list jobs
    assert await _list_in_workflow(Tokens('foo/run2//1/foo/')) == {
        'foo/run2//1/foo/01/',
        'foo/run2//1/foo/NN/',
    }
    # jobs => nothing to do
    assert await _list_in_workflow(
        Tokens('foo/run2//1/foo/01'),
    ) == set()

    # no tokens => nothing to list
    assert await _list_in_workflow(Tokens()) == set()
    # non-existant workflow => nothing to list
    assert await _list_in_workflow(
        Tokens('forty-two'),
        # set infer_run to false as this workflow does not exist so will raise
        # an exception
        # (note exceptions are fine, they get caught and ignored at the top
        # level)
        infer_run=False
    ) == set()
    # non-existant cycle => nothing to list
    assert await _list_in_workflow(Tokens('foo/run2//4')) == set()
    # non-existant task => nothing to list
    assert await _list_in_workflow(Tokens('foo/run2//4/foo')) == set()
    # non-existant job => nothing to list
    assert await _list_in_workflow(Tokens('foo/run2//4/foo/02')) == set()


async def test_list_in_workflow_inference(dummy_workflow):
    """It should infer the latest run when appropriate."""
    _list_in_workflow = setify(list_in_workflow)

    assert await _list_in_workflow(Tokens('foo/run2//')) == {
        'foo/run2//1/',
        'foo/run2//2/',
        'foo/run2//3/',
    }
    assert await _list_in_workflow(Tokens('foo//')) == {
        'foo//1/',
        'foo//2/',
        'foo//3/',
    }


async def test_list_resources():
    """Test listing of "resources.

    Resources i.e. things provided by `cylc get-resources`.
    """
    assert 'cylc-completion.bash' in await list_resources(None)


async def test_list_dir(tmp_path, monkeypatch):
    """Test directory listing."""
    (tmp_path / 'x').mkdir()
    ((tmp_path / 'x') / 'y').mkdir()
    ((tmp_path / 'x') / 'z').touch()
    monkeypatch.chdir(tmp_path)

    _list_dir = setify(list_dir)

    # --- relative paths ---

    # no "partial"
    # => list $PWD
    assert {
        str(path)
        for path in await _list_dir(None)
    } == {'x/'}

    # no trailing `/` at the end of the path
    # (i.e. an incomplete path)
    # => list the parent
    assert {
        str(path)
        for path in await _list_dir('x')
    } == {'x/'}

    # # trailing `/` at the end of the path
    # # (i.e. complete path)
    # # => list dir path
    assert {
        str(path)
        for path in await _list_dir('x/')
    } == {'x/y/', 'x/z'}  # "y" is a dir, "z" is a file

    # listing a file
    # => noting to list, just return the file
    assert {
        str(path)
        for path in await _list_dir('x/z/')
    } == {'x/z'}

    # --- absolute paths ---

    # no trailing `/` at the end of the path
    # (i.e. an incomplete path)
    # => list the parent
    assert {
        # '/'.join(path.rsplit('/', 2)[-2:])
        path.replace(str(tmp_path), '')
        for path in await _list_dir(str(tmp_path / 'x'))
    } == {'/x/'}

    # trailing `/` at the end of the path
    # (i.e. complete path)
    # => list dir path
    assert {
        path.replace(str(tmp_path), '')
        for path in await _list_dir(str(tmp_path / 'x') + '/')
    } == {'/x/y/', '/x/z'}  # "y" is a dir, "z" is a file

    # listing a file
    # => noting to list, just return the file
    assert {
        path.replace(str(tmp_path), '')
        for path in await _list_dir(str(tmp_path / 'x' / 'z') + '/')
    } == {'/x/z'}


async def test_list_flows():
    """Test listing values for the --flow option.

    Currently this only provides the textural options i.e. it doesn't list
    "flows" running in a workflow, yet...
    """
    assert 'all' in await list_flows(None)


async def test_list_colours():
    """Test listing values for the --color option."""
    assert 'always' in await list_colours(None)


async def test_cli_detokenise():
    """Test that Cylc IDs are detokenised with a trailing slash.

    Cylc completion used the trailing slash to determine that the previous
    part of the ID has been completed the same way as regular directory
    completion does.
    """

    assert cli_detokenise(Tokens()) == ''
    assert cli_detokenise(Tokens('~u/w')) == '~u/w//'
    assert cli_detokenise(Tokens('~u/w//c')) == '~u/w//c/'
    assert cli_detokenise(Tokens('~u/w//c/t')) == '~u/w//c/t/'
    assert cli_detokenise(Tokens('~u/w//c/t/01')) == '~u/w//c/t/01/'


def test_get_completion_script_file():
    """Test retrieving the completion script file."""
    assert get_completion_script_file('bash').exists()
    # if the requested language is not supported it should return None
    assert get_completion_script_file('ksh') is None


def test_get_current_completion_script_version(tmp_path):
    """Test extracting the completion script version from the script file.

    We do this to determine the version of the completion script bundled with
    this version of Cylc (in order to inform users of upgrades).
    """
    completion_script = get_completion_script_file('bash')

    # it should extract the version for bash
    assert get_current_completion_script_version(
        completion_script,
        'bash',
    ) is not None

    # it should return None for ksh
    assert get_current_completion_script_version(
        completion_script,
        'ksh',
    ) is None

    # it should return None if it can't find the version
    completion_script = (tmp_path / 'foo')
    completion_script.touch()
    assert get_current_completion_script_version(
        completion_script,
        'bash',
    ) is None


def test_check_completion_script_compatibility(monkeypatch, capsys):
    """Test whether a completion script is compatible with the server.

    Incase the server interface changes at a later date this will allow us to
    exit gracefully rather than crashing in a horrible way.
    """
    # set the bash completion script version to 1.0.1
    def _get_current_completion_script_version(_script, lang):
        if lang == 'bash':
            return '1.0.1'
        return None

    # set the completion script compatibility range to >=1.0.0, <2.0.0
    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server.REQUIRED_SCRIPT_VERSION',
        '>=1.0.0, <2.0.0',
    )
    monkeypatch.setattr(
        'cylc.flow.scripts.completion_server'
        '.get_current_completion_script_version',
        _get_current_completion_script_version
    )

    # versions which match ">=1.0.0, <2.0.0" should be valid
    assert check_completion_script_compatibility('bash', '0.9.9') is False
    assert check_completion_script_compatibility('bash', '1.0.0') is True
    assert check_completion_script_compatibility('bash', '1.0.1') is True
    assert check_completion_script_compatibility('bash', '1.0.2') is True
    assert check_completion_script_compatibility('bash', '2.0.0') is False

    # all versions should be invalid (because we don't offer ksh support)
    assert check_completion_script_compatibility('ksh', '0.9.9') is False
    assert check_completion_script_compatibility('ksh', '1.0.0') is False
    assert check_completion_script_compatibility('ksh', '1.0.1') is False
    assert check_completion_script_compatibility('ksh', '1.0.2') is False
    assert check_completion_script_compatibility('ksh', '2.0.0') is False

    # it should tell the user when a new version of the script is available
    capsys.readouterr()  # clear
    assert check_completion_script_compatibility('bash', '1.0.0') is True
    out, err = capsys.readouterr()
    assert not out  # never write to stdout
    assert 'A new version of the Cylc bash script is available' in err

    # it should tell the user if the script is incompatible
    capsys.readouterr()  # clear
    assert check_completion_script_compatibility('bash', '0.9.9') is False
    out, err = capsys.readouterr()
    assert not out  # never write to stdout
    assert 'The Cylc bash script needs to be updated' in err

    # it shouldn't say anything unless necessary
    capsys.readouterr()  # clear
    assert check_completion_script_compatibility('bash', '1.0.1') is True
    out, err = capsys.readouterr()
    assert not out  # never write to stdout
    assert not err


async def test_prereqs_and_outputs():
    """Test the error cases for listing task prereqs/outputs.

    The succeess cases are tested in an integration test (requires a running
    scheduler).
    """
    # if no tokens are provided, no prereqs or outputs are returned
    assert await _list_prereqs_and_outputs([]) == ([], [])

    # if an invalid workflow is provided, we can't list anything
    assert await _list_prereqs_and_outputs([Tokens(workflow='no-such-workflow')]) == ([], [])
