# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
import os.path
from pathlib import Path
import pytest
from unittest import mock

from cylc.flow import CYLC_LOG
from cylc.flow import suite_files
from cylc.flow.exceptions import (
    CylcError, SuiteServiceFileError, TaskRemoteMgmtError, WorkflowFilesError)
from cylc.flow.suite_files import check_nested_run_dirs


def get_register_test_cases():
    """Test cases for suite_files.register function."""
    return [
        # 1 no parameters provided, current directory is not a symlink,
        # and contains a valid flow.cylc
        (None,  # reg
         None,  # source
         False,  # redirect,
         "/home/user/cylc-run/suite1",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite1/.service",  # suite_srv_dir
         "/home/user/cylc-run/suite1",  # readlink
         None,  # expected symlink
         "suite1",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 2 suite name provided, current directory is not a symlink,
        # and contains a valid flow.cylc
        ("super-suite-2",  # reg
         None,  # source
         False,  # redirect,
         "/home/user/cylc-run/suite2",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite2/.service",  # suite_srv_dir
         "/home/user/cylc-run/suite2",  # readlink
         None,  # expected symlink
         "super-suite-2",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 3 suite name and directory location of flow.cylc provided,
        # current directory is not a symlink, and contains a valid flow.cylc
        ("suite3",  # reg
         "/home/user/cylc-run/suite3/flow.cylc",  # source
         False,  # redirect,
         "/home/user/cylc-run/suite3",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite3/.service",  # suite_srv_dir
         "/home/user/cylc-run/suite3",  # readlink
         None,  # expected symlink
         "suite3",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 4 suite name and directory location of flow.cylc provided,
        # current directory is not a symlink, but the flow.cylc does not
        # exist
        ("suite4",  # reg
         "/home/user/cylc-run/suite4/suite.txt",  # source
         False,  # redirect,
         "/home/user/cylc-run/suite4",  # cwd
         False,  # isabs
         False,  # isfile
         "/home/user/cylc-run/suite4/.service",  # suite_srv_dir
         "/home/user/cylc-run/suite4",  # readlink
         None,  # expected symlink
         "suite4",  # expected return value
         SuiteServiceFileError,  # expected exception
         "no flow.cylc"  # expected part of exception message
         ),
        # 5 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. No redirect
        # specified, so it must raise an error
        ("suite5",  # reg
         "/home/user/cylc-run/suite5/suite.txt",  # source
         False,  # redirect,
         "/home/user/cylc-run/suite5",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite5/.service",  # suite_srv_dir
         "/home/hercules/cylc-run/suite5",  # readlink
         "/home/user/cylc-run/suite5",  # expected symlink
         "suite5",  # expected return value
         SuiteServiceFileError,  # expected exception
         "already points to"  # expected part of exception message
         ),
        # 6 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. The redirect
        # flag is true, so it must simply delete the old source link
        ("suite6",  # reg
         "/home/user/cylc-run/suite6/flow.cylc",  # source
         True,  # redirect,
         "/home/user/cylc-run/suite6",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/hercules/cylc-run/suite6/.service",  # suite_srv_dir
         "/home/hercules/cylc-run/suite6",  # readlink
         "/home/user/cylc-run/suite6",  # expected symlink
         "suite6",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 7 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. The redirect
        # flag is true. But the resolved orig_source's parent directory,
        # is the source directory. So the symlink must be '..'
        ("suite7",  # reg
         "/home/user/cylc-run/suite7/flow.cylc",  # source
         True,  # redirect,
         "/home/user/cylc-run/suite7",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite7/.service",  # suite_srv_dir
         "/home/user/cylc-run/suites/suite7",  # readlink
         "..",  # expected symlink
         "suite7",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 8 fails to readlink, resulting in a new symlink created
        ("suite8",  # reg
         "/home/user/cylc-run/suite8/flow.cylc",  # source
         False,  # redirect,
         "/home/user/cylc-run/suite8",  # cwd
         False,  # isabs
         True,  # isfile
         "/home/user/cylc-run/suite8/.service",  # suite_srv_dir
         OSError,  # readlink
         "..",  # expected symlink
         "suite8",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 9 the suite name is an absolute path
        ("/suite9/",  # reg
         None,  # source
         False,  # redirect,
         None,  # cwd
         True,  # isabs
         True,  # isfile
         None,  # suite_srv_dir
         None,  # readlink
         None,  # expected symlink
         None,  # expected return value
         SuiteServiceFileError,  # expected exception
         "cannot be an absolute path"  # expected part of exception message
         ),
        # 10 invalid suite name
        ("-foo",  # reg
         None,  # source
         False,  # redirect,
         None,  # cwd
         True,  # isabs
         True,  # isfile
         None,  # suite_srv_dir
         None,  # readlink
         None,  # expected symlink
         None,  # expected return value
         SuiteServiceFileError,  # expected exception
         "cannot start with: ``.``, ``-``"  # expected part of exception msg
         )
    ]


@mock.patch('cylc.flow.suite_files.make_localhost_symlinks')
@mock.patch('os.unlink')
@mock.patch('os.makedirs')
@mock.patch('os.symlink')
@mock.patch('os.readlink')
@mock.patch('os.path.isfile')
@mock.patch('os.path.isabs')
@mock.patch('os.getcwd')
@mock.patch('os.path.abspath')
@mock.patch('cylc.flow.suite_files.get_suite_srv_dir')
@mock.patch('cylc.flow.suite_files.check_nested_run_dirs')
def test_register(mocked_check_nested_run_dirs,
                  mocked_get_suite_srv_dir,
                  mocked_abspath,
                  mocked_getcwd,
                  mocked_isabs,
                  mocked_isfile,
                  mocked_readlink,
                  mocked_symlink,
                  mocked_makedirs,
                  mocked_unlink,
                  mocked_make_localhost_symlinks
                  ):
    """Test the register function."""
    def mkdirs_standin(_, exist_ok=False):
        return True

    mocked_abspath.side_effect = lambda x: x
    # mocked_check_nested_run_dirs - no side effect as we're just ignoring it

    for (reg, source, redirect, cwd, isabs, isfile, suite_srv_dir,
            readlink, expected_symlink, expected, e_expected,
            e_message) in get_register_test_cases():
        mocked_getcwd.side_effect = lambda: cwd
        mocked_isabs.side_effect = lambda x: isabs

        mocked_isfile.side_effect = lambda x: isfile
        mocked_get_suite_srv_dir.return_value = str(suite_srv_dir)
        mocked_makedirs.return_value = True
        mocked_unlink.return_value = True
        if readlink == OSError:
            mocked_readlink.side_effect = readlink
        else:
            mocked_readlink.side_effect = lambda x: readlink

        if e_expected is None:
            reg = suite_files.install(reg, source, redirect)
            assert reg == expected
            if mocked_symlink.call_count > 0:
                # first argument, of the first call
                arg0 = mocked_symlink.call_args[0][0]
                assert arg0 == expected_symlink
        else:
            with pytest.raises(e_expected) as exc:
                suite_files.install(reg, source, redirect)
            if e_message is not None:
                assert e_message in str(exc.value)


@pytest.mark.parametrize(
    'path, expected',
    [('a/b/c', '/mock_cylc_dir/a/b/c'),
     ('/a/b/c', '/a/b/c')]
)
def test_get_cylc_run_abs_path(path, expected, monkeypatch):
    monkeypatch.setattr('cylc.flow.pathutil.get_platform',
                        lambda: {'run directory': '/mock_cylc_dir'})
    assert suite_files.get_cylc_run_abs_path(path) == expected


@pytest.mark.parametrize(
    'path, expected',
    [('service/dir/exists', True),
     ('flow/file/exists', False),  # Non-run dirs can still contain flow.cylc
     ('nothing/exists', False)]
)
@pytest.mark.parametrize('is_abs_path', [False, True])
def test_is_valid_run_dir(path, expected, is_abs_path, monkeypatch):
    """Test that a directory is correctly identified as a valid run dir when
    it contains a service dir.
    """
    prefix = os.sep if is_abs_path is True else 'mock_cylc_dir'
    flow_file = os.path.join(prefix, 'flow', 'file', 'exists', 'flow.cylc')
    serv_dir = os.path.join(prefix, 'service', 'dir', 'exists', '.service')
    monkeypatch.setattr('os.path.isfile', lambda x: x == flow_file)
    monkeypatch.setattr('os.path.isdir', lambda x: x == serv_dir)
    monkeypatch.setattr('cylc.flow.pathutil.get_platform',
                        lambda: {'run directory': 'mock_cylc_dir'})
    path = os.path.normpath(path)
    if is_abs_path:
        path = os.path.join(os.sep, path)

    assert suite_files.is_valid_run_dir(path) is expected, (
        f'Is "{path}" a valid run dir?')


@pytest.mark.parametrize('direction', ['parents', 'children'])
def test_nested_run_dirs_raise_error(direction, monkeypatch):
    """Test that a suite cannot be contained in a subdir of another suite."""
    monkeypatch.setattr('cylc.flow.suite_files.get_cylc_run_abs_path',
                        lambda x: x)
    if direction == "parents":
        monkeypatch.setattr('cylc.flow.suite_files.os.scandir', lambda x: [])
        monkeypatch.setattr('cylc.flow.suite_files.is_valid_run_dir',
                            lambda x: x == os.path.join('bright', 'falls'))
        # Not nested in run dir - ok:
        suite_files.check_nested_run_dirs('alan/wake')
        # It is itself a run dir - ok:
        suite_files.check_nested_run_dirs('bright/falls')
        # Nested in a run dir - bad:
        for path in ('bright/falls/light', 'bright/falls/light/and/power'):
            with pytest.raises(WorkflowFilesError) as exc:
                suite_files.check_nested_run_dirs(path)
            assert 'Nested run directories not allowed' in str(exc.value)

    else:
        dirs = ['a', 'a/a', 'a/R', 'a/a/a', 'a/a/R',
                'a/b', 'a/b/a', 'a/b/b',
                'a/c', 'a/c/a', 'a/c/a/a', 'a/c/a/a/a', 'a/c/a/a/a/R',
                'a/d', 'a/d/a', 'a/d/a/a', 'a/d/a/a/a', 'a/d/a/a/a/a',
                'a/d/a/a/a/a/R']
        run_dirs = [d for d in dirs if 'R' in d]

        def mock_scandir(path):
            return [mock.Mock(path=d, is_dir=lambda: True,
                              is_symlink=lambda: False) for d in dirs
                    if (d.startswith(path) and len(d) == len(path) + 2)]
        monkeypatch.setattr('cylc.flow.suite_files.os.scandir', mock_scandir)
        monkeypatch.setattr('cylc.flow.suite_files.os.path.isdir',
                            lambda x: x in dirs)
        monkeypatch.setattr('cylc.flow.suite_files.is_valid_run_dir',
                            lambda x: x in run_dirs)

        # No run dir nested below - ok:
        for path in ('a/a/a', 'a/b'):
            suite_files.check_nested_run_dirs(path)
        # Run dir nested below - bad:

        for path in ('a', 'a/a', 'a/c'):
            with pytest.raises(WorkflowFilesError) as exc:
                check_nested_run_dirs(path)
            assert 'Nested run directories not allowed' in str(exc.value)
        for func in (suite_files.check_nested_run_dirs, suite_files.install):
            for path in ('a', 'a/a', 'a/c'):
                with pytest.raises(SuiteServiceFileError) as exc:
                    func(path)
                assert 'Nested run directories not allowed' in str(exc.value)
        # Run dir nested below max scan depth - not ideal but passes:
        suite_files.check_nested_run_dirs('a/d')


@pytest.mark.parametrize(
    'reg, expected_err, expected_msg',
    [('foo/bar/', None, None),
     ('/foo/bar', SuiteServiceFileError, "cannot be an absolute path"),
     ('$HOME/alone', SuiteServiceFileError, "invalid suite name")]
)
def test_validate_reg(reg, expected_err, expected_msg):
    if expected_err:
        with pytest.raises(expected_err) as exc:
            suite_files._validate_reg(reg)
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        suite_files._validate_reg(reg)


@pytest.mark.parametrize(
    'reg, not_stopped, err, err_msg',
    [('foo/..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo/../..', False, WorkflowFilesError,
      "cannot be a path that points to the cylc-run directory or above"),
     ('foo', True, SuiteServiceFileError, "Cannot remove running workflow")]
)
def test_clean_check(reg, not_stopped, err, err_msg, monkeypatch):
    """Test that _clean_check() fails appropriately.

    Params:
        reg (str): Workflow name.
        err (Exception): Expected error.
        err_msg (str): Message that is expected to be in the exception.
    """
    run_dir = mock.Mock()

    def mocked_detect_old_contact_file(reg):
        if not_stopped:
            raise SuiteServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.suite_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)

    with pytest.raises(err) as exc:
        suite_files._clean_check(reg, run_dir)
    assert err_msg in str(exc.value)


@pytest.mark.parametrize(
    'reg, props, clean_called, remote_clean_called',
    [
        ('foo/bar', {
            'no dir': True,
            'log': (logging.INFO, "No directory to clean")
        }, False, False),
        ('foo/bar', {
            'no db': True,
            'log': (logging.INFO,
                    "No workflow database - will only clean locally")
        }, True, False),
        ('foo/bar', {
            'db platforms': ['localhost', 'localhost']
        }, True, False),
        ('foo/bar', {
            'db platforms': ['horse']
        }, True, True)
    ]
)
def test_init_clean_ok(
        reg, props, clean_called, remote_clean_called,
        monkeypatch, tmp_path, caplog):
    """Test the init_clean() function logic.

    Params:
        reg (str): Workflow name.
        props (dict): Possible values are (all optional):
            'no dir' (bool): If True, do not create run dir for this test case.
            'log' (tuple): Of form (severity, msg):
                severity (logging level): Expected level e.g. logging.INFO.
                msg (str): Message that is expected to be logged.
            'db platforms' (list): Platform names that would be loaded from
                the database.
            'no db' (bool): If True, workflow database doesn't exist.
        clean_called (bool): If a local clean is expected to go ahead.
        remote_clean_called (bool): If a remote clean is expected to go ahead.
    """
    # --- Setup ---
    expected_log = props.get('log')
    if expected_log:
        level, msg = expected_log
        caplog.set_level(level, CYLC_LOG)

    tmp_path.joinpath('cylc-run').mkdir()
    run_dir = tmp_path.joinpath('cylc-run', reg)
    if not props.get('no dir'):
        run_dir.mkdir(parents=True)

    mocked_clean = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.clean', mocked_clean)
    mocked_remote_clean = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.remote_clean',
                        mocked_remote_clean)
    monkeypatch.setattr('cylc.flow.suite_files.get_suite_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    _get_platforms_from_db = suite_files.get_platforms_from_db

    def mocked_get_platforms_from_db(run_dir):
        if props.get('no dir') or props.get('no db'):
            return _get_platforms_from_db(run_dir)  # Handle as normal
        return set(props.get('db platforms'))

    monkeypatch.setattr('cylc.flow.suite_files.get_platforms_from_db',
                        mocked_get_platforms_from_db)

    # --- The actual test ---
    suite_files.init_clean(reg, opts=mock.Mock())
    if expected_log:
        assert msg in caplog.text
    if clean_called:
        assert mocked_clean.called is True
    else:
        assert mocked_clean.called is False
    if remote_clean_called:
        assert mocked_remote_clean.called is True
    else:
        assert mocked_remote_clean.called is False


@pytest.mark.parametrize(
    'reg, props',
    [
        ('foo/bar/', {}),  # Works ok
        ('foo', {'no dir': True}),  # Nothing to clean
        ('foo', {
            'not stopped': True,
            'err': SuiteServiceFileError,
            'err msg': 'Cannot remove running workflow'
        }),
        ('foo/bar', {
            'symlink dirs': {
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            }
        }),
        ('foo', {
            'symlink dirs': {
                'run': 'sym-run',
                'log': 'sym-log',
                'share': 'sym-share',
                'share/cycle': 'sym-cycle',
                'work': 'sym-work'
            }
        }),
        ('foo', {
            'bad symlink': {
                'type': 'file',
                'path': 'sym-log/cylc-run/foo/meow.txt'
            },
            'err': WorkflowFilesError,
            'err msg': 'Target is not a directory'
        }),
        ('foo', {
            'bad symlink': {
                'type': 'dir',
                'path': 'sym-log/bad/path'
            },
            'err': WorkflowFilesError,
            'err msg': 'Expected target to end with "cylc-run/foo/log"'
        })
    ]
)
def test_clean(reg, props, monkeypatch, tmp_path):
    """Test the clean() function.

    Params:
        reg (str): Workflow name.
        props (dict): Possible values are (all optional):
            'err' (Exception): Expected error.
            'err msg' (str): Message that is expected to be in the exception.
            'no dir' (bool): If True, do not create run dir for this test case.
            'not stopped' (bool): If True, simulate that the workflow is
                still running.
            'symlink dirs' (dict): As you would find in the global config
                under [symlink dirs][platform].
            'bad symlink' (dict): Simulate an invalid log symlink dir:
                'type' (str): 'file' or 'dir'.
                'path' (str): Path of the symlink target relative to tmp_path.
    """
    # --- Setup ---
    tmp_path.joinpath('cylc-run').mkdir()
    run_dir = tmp_path.joinpath('cylc-run', reg)
    run_dir_top_parent = tmp_path.joinpath('cylc-run', Path(reg).parts[0])
    symlink_dirs = props.get('symlink dirs')
    bad_symlink = props.get('bad symlink')
    if not props.get('no dir') and (
            not symlink_dirs or 'run' not in symlink_dirs):
        run_dir.mkdir(parents=True)

    dirs_to_check = [run_dir_top_parent]
    if symlink_dirs:
        if 'run' in symlink_dirs:
            dst = tmp_path.joinpath(symlink_dirs['run'], 'cylc-run', reg)
            dst.mkdir(parents=True)
            run_dir.symlink_to(dst)
            dirs_to_check.append(dst)
            symlink_dirs.pop('run')
        for s, d in symlink_dirs.items():
            dst = tmp_path.joinpath(d, 'cylc-run', reg, s)
            dst.mkdir(parents=True)
            src = run_dir.joinpath(s)
            src.symlink_to(dst)
            dirs_to_check.append(dst.parent)
    if bad_symlink:
        dst = tmp_path.joinpath(bad_symlink['path'])
        if bad_symlink['type'] == 'file':
            dst.parent.mkdir(parents=True)
            dst.touch()
        else:
            dst.mkdir(parents=True)
        src = run_dir.joinpath('log')
        src.symlink_to(dst)

    def mocked_detect_old_contact_file(reg):
        if props.get('not stopped'):
            raise SuiteServiceFileError('Mocked error')

    monkeypatch.setattr('cylc.flow.suite_files.detect_old_contact_file',
                        mocked_detect_old_contact_file)
    monkeypatch.setattr('cylc.flow.suite_files.get_suite_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    # --- The actual test ---
    expected_err = props.get('err')
    if expected_err:
        with pytest.raises(expected_err) as exc:
            suite_files.clean(reg)
        expected_msg = props.get('err msg')
        if expected_msg:
            assert expected_msg in str(exc.value)
    else:
        suite_files.clean(reg)
        for d in dirs_to_check:
            assert d.exists() is False
            assert d.is_symlink() is False


def test_clean_broken_symlink_run_dir(monkeypatch, tmp_path):
    """Test clean() for removing a run dir that is a broken symlink."""
    reg = 'foo/bar'
    run_dir = tmp_path.joinpath('cylc-run', reg)
    run_dir.parent.mkdir(parents=True)
    target = tmp_path.joinpath('rabbow/cylc-run', reg)
    target.mkdir(parents=True)
    run_dir.symlink_to(target)
    target.rmdir()

    monkeypatch.setattr('cylc.flow.suite_files.get_suite_run_dir',
                        lambda x: tmp_path.joinpath('cylc-run', x))

    suite_files.clean(reg)
    assert run_dir.parent.is_dir() is False


PLATFORMS = {
    'enterprise': {
        'hosts': ['kirk', 'picard'],
        'install target': 'picard',
        'name': 'enterprise'
    },
    'voyager': {
        'hosts': ['janeway'],
        'install target': 'janeway',
        'name': 'voyager'
    },
    'stargazer': {
        'hosts': ['picard'],
        'install target': 'picard',
        'name': 'stargazer'
    },
    'exeter': {
        'hosts': ['localhost'],
        'install target': 'localhost',
        'name': 'exeter'
    }
}


@pytest.mark.parametrize(
    'install_targets_map, failed_platforms, expected_platforms, expected_err',
    [
        (
            {'localhost': [PLATFORMS['exeter']]}, None, None, None
        ),
        (
            {
                'localhost': [PLATFORMS['exeter']],
                'picard': [PLATFORMS['enterprise']]
            },
            None,
            ['enterprise'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            None,
            ['enterprise', 'voyager'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise'],
            ['enterprise', 'stargazer', 'voyager'],
            None
        ),
        (
            {
                'picard': [PLATFORMS['enterprise'], PLATFORMS['stargazer']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise', 'stargazer'],
            ['enterprise', 'stargazer', 'voyager'],
            (CylcError, "Could not clean on install targets: picard")
        ),
        (
            {
                'picard': [PLATFORMS['enterprise']],
                'janeway': [PLATFORMS['voyager']]
            },
            ['enterprise', 'voyager'],
            ['enterprise', 'voyager'],
            (CylcError, "Could not clean on install targets: picard, janeway")
        )
    ]
)
def test_remote_clean(install_targets_map, failed_platforms,
                      expected_platforms, expected_err, monkeypatch, caplog):
    """Test remote_clean() logic.

    Params:
        install_targets_map (dict): The map that would be returned by
            platforms.get_install_target_to_platforms_map()
        failed_platforms (list): If specified, any platforms that clean will
            artificially fail on in this test case.
        expected_platforms (list): If specified, all the platforms that the
            remote clean cmd is expected to run on.
        expected_err (tuple):  If specified, a tuple of the form
            (Exception, str) giving an exception that is expected to be raised.
    """
    # ----- Setup -----
    caplog.set_level(logging.DEBUG, CYLC_LOG)
    monkeypatch.setattr(
        'cylc.flow.suite_files.get_install_target_to_platforms_map',
        lambda x: install_targets_map)
    # Remove randomness:
    mocked_shuffle = mock.Mock()
    monkeypatch.setattr('cylc.flow.suite_files.shuffle', mocked_shuffle)

    def mocked_remote_clean_cmd_side_effect(reg, platform, timeout):
        proc_ret_code = 0
        if failed_platforms and platform['name'] in failed_platforms:
            proc_ret_code = 1
        return mock.Mock(
            poll=lambda: proc_ret_code,
            communicate=lambda: (b"", b""),
            args=[])

    mocked_remote_clean_cmd = mock.Mock(
        side_effect=mocked_remote_clean_cmd_side_effect)
    monkeypatch.setattr(
        'cylc.flow.suite_files._remote_clean_cmd', mocked_remote_clean_cmd)
    # ----- Test -----
    reg = 'foo'
    platform_names = (
        "This arg bypassed as we provide the install targets map in the test")
    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            suite_files.remote_clean(reg, platform_names, timeout='irrelevant')
        assert msg in str(exc.value)
    else:
        suite_files.remote_clean(reg, platform_names, timeout='irrelevant')
    if expected_platforms:
        for p_name in expected_platforms:
            mocked_remote_clean_cmd.assert_any_call(
                reg, PLATFORMS[p_name], 'irrelevant')
    else:
        mocked_remote_clean_cmd.assert_not_called()
    if failed_platforms:
        for p_name in failed_platforms:
            assert f"{p_name}: {TaskRemoteMgmtError.MSG_TIDY}" in caplog.text


def test_remove_empty_reg_parents(tmp_path):
    """Test that _remove_empty_parents() doesn't remove parents containing a
    sibling."""
    reg = 'foo/bar/baz/qux'
    path = tmp_path.joinpath(reg)
    tmp_path.joinpath('foo/bar/baz').mkdir(parents=True)
    sibling_reg = 'foo/darmok'
    sibling_path = tmp_path.joinpath(sibling_reg)
    sibling_path.mkdir()
    suite_files._remove_empty_reg_parents(reg, path)
    assert tmp_path.joinpath('foo/bar').exists() is False
    assert tmp_path.joinpath('foo').exists() is True
    # Also path must be absolute
    with pytest.raises(ValueError) as exc:
        suite_files._remove_empty_reg_parents('foo/darmok', 'meow/foo/darmok')
    assert 'Path must be absolute' in str(exc.value)
    # Check it skips non-existent dirs, and stops at the right place too
    tmp_path.joinpath('foo/bar').mkdir()
    sibling_path.rmdir()
    suite_files._remove_empty_reg_parents(reg, path)
    assert tmp_path.joinpath('foo').exists() is False
    assert tmp_path.exists() is True
