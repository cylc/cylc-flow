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

from cylc.flow.suite_files import check_nested_run_dirs
import pytest
from unittest import mock

import os.path
from pathlib import Path
from cylc.flow import suite_files
from cylc.flow.exceptions import SuiteServiceFileError, WorkflowFilesError


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
            reg = suite_files.register(reg, source, redirect)
            assert reg == expected
            if mocked_symlink.call_count > 0:
                # first argument, of the first call
                arg0 = mocked_symlink.call_args[0][0]
                assert arg0 == expected_symlink
        else:
            with pytest.raises(e_expected) as exc:
                suite_files.register(reg, source, redirect)
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
        # Run dir nested below max scan depth - not ideal but passes:
        suite_files.check_nested_run_dirs('a/d')


@pytest.mark.parametrize(
    'reg, expected_err',
    [('foo/bar/', None),
     ('/foo/bar', SuiteServiceFileError)]
)
def test_validate_reg(reg, expected_err):
    if expected_err:
        with pytest.raises(expected_err) as exc:
            suite_files._validate_reg(reg)
        assert 'cannot be an absolute path' in str(exc.value)
    else:
        suite_files._validate_reg(reg)


@pytest.mark.parametrize(
    'reg, props',
    [
        ('foo/bar/', {}),
        ('foo/..', {
            'no dir': True,
            'err': WorkflowFilesError,
            'err msg': ('cannot be a path that points to the cylc-run '
                        'directory or above')
        }),
        ('foo/../..', {
            'no dir': True,
            'err': WorkflowFilesError,
            'err msg': ('cannot be a path that points to the cylc-run '
                        'directory or above')
        }),
        ('foo', {
            'not stopped': True,
            'err': SuiteServiceFileError,
            'err msg': 'Cannot remove running workflow'
        }),
        ('foo', {
            'no dir': True,
            'err': WorkflowFilesError,
            'err msg': 'No directory found'
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
