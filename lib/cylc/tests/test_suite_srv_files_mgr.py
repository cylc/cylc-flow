#!/usr/bin/env python2

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

import errno
import os
import pytest

import mock

from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager,
    SuiteServiceFileError,
    SuiteCylcVersionError
)


def makedirs(path, exist_ok=False):
    if not exist_ok:
        os.makedirs(path)
    else:
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise exc


@pytest.mark.parametrize(
    ('reg', 'source', 'redirect', 'cwd', 'suiterc_exists', 'suite_srv_dir',
     'readlink', 'expected_symlink', 'expected', 'e_expected', 'e_message'),
    [
        # 1 no parameters provided, current directory is not a symlink,
        # and contains a valid suite.rc
        (None,  # reg
         None,  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite1",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite1/.service",  # suite_srv_dir
         "{home}/user/cylc-run/suite1",  # readlink
         None,  # expected symlink
         "suite1",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 2 suite name provided, current directory is not a symlink,
        # and contains a valid suite.rc
        ("super-suite-2",  # reg
         None,  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite2",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite2/.service",  # suite_srv_dir
         "{home}/user/cylc-run/suite2",  # readlink
         None,  # expected symlink
         "super-suite-2",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 3 suite name and directory location of suite.rc provided,
        # current directory is not a symlink, and contains a valid suite.rc
        ("suite3",  # reg
         "{home}/user/cylc-run/suite3/suite.rc",  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite3",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite3/.service",  # suite_srv_dir
         "{home}/user/cylc-run/suite3",  # readlink
         None,  # expected symlink
         "suite3",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 4 suite name and directory location of suite.rc provided,
        # current directory is not a symlink, but the suite.rc does not
        # exist
        ("suite4",  # reg
         "{home}/user/cylc-run/suite4/suite.txt",  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite4",  # cwd
         False,  # suiterc_exists
         "{home}/user/cylc-run/suite4/.service",  # suite_srv_dir
         "{home}/user/cylc-run/suite4",  # readlink
         None,  # expected symlink
         "suite4",  # expected return value
         SuiteServiceFileError,  # expected exception
         "no suite.rc"  # expected part of exception message
         ),
        # 5 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. No redirect
        # specified, so it must raise an error
        ("suite5",  # reg
         "{home}/user/cylc-run/suite5",  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite5",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite5/.service",  # suite_srv_dir
         "{home}/hercules/cylc-run/suite5",  # readlink
         "{home}/user/cylc-run/suite5",  # expected symlink
         "suite5",  # expected return value
         SuiteServiceFileError,  # expected exception
         "already points to"  # expected part of exception message
         ),
        # 6 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. The redirect
        # flag is true, so it must simply delete the old source link
        ("suite6",  # reg
         "{home}/user/cylc-run/suite6/suite.rc",  # source
         True,  # redirect,
         "{home}/user/cylc-run/suite6",  # cwd
         True,  # suiterc_exists
         "{home}/hercules/cylc-run/suite6/.service",  # suite_srv_dir
         "{home}/hercules/cylc-run/suite6",  # readlink
         "{home}/user/cylc-run/suite6",  # expected symlink
         "suite6",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 7 the source directory and the resolved symlink for $SOURCE in
        # $SOURCE/.service are not the same directory. The redirect
        # flag is true. But the resolved orig_source's parent directory,
        # is the source directory. So the symlink must be '..'
        ("suite7",  # reg
         "{home}/user/cylc-run/suite7/suite.rc",  # source
         True,  # redirect,
         "{home}/user/cylc-run/suite7",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite7/.service",  # suite_srv_dir
         "{home}/user/cylc-run/suites/suite7",  # readlink
         "..",  # expected symlink
         "suite7",  # expected return value
         None,  # expected exception
         None  # expected part of exception message
         ),
        # 8 fails to readlink, resulting in a new symlink created
        ("suite8",  # reg
         "{home}/user/cylc-run/suite8/suite.rc",  # source
         False,  # redirect,
         "{home}/user/cylc-run/suite8",  # cwd
         True,  # suiterc_exists
         "{home}/user/cylc-run/suite8/.service",  # suite_srv_dir
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
         True,  # suiterc_exists
         None,  # suite_srv_dir
         None,  # readlink
         None,  # expected symlink
         None,  # expected return value
         SuiteServiceFileError,  # expected exception
         "cannot be an absolute path"  # expected part of exception message
         )
    ]
)
@mock.patch('cylc.suite_srv_files_mgr.mkdir_p')
def test_register(
    mocked_mkdir_p,
    reg, source, redirect, cwd, suiterc_exists, suite_srv_dir,
    readlink, expected_symlink, expected, e_expected, e_message,
    monkeypatch, tmp_path
):
    """Test the SuiteSrvFilesManager register function."""
    # --- Setup ---
    mocked_mkdir_p.side_effect = lambda x: True
    if cwd:
        cwd = cwd.format(home=tmp_path)
        makedirs(cwd)
    else:
        cwd = str(tmp_path)
    monkeypatch.chdir(cwd)
    if source:
        source = source.format(home=tmp_path)
        if '.' in os.path.basename(source):
            source_dir = os.path.dirname(source)
        else:
            source_dir = source
        makedirs(source_dir, exist_ok=True)
    if suiterc_exists:
        if not source:
            source_dir = cwd
        suiterc_file = os.path.join(source_dir, 'suite.rc')
        with open(suiterc_file, 'w'):
            pass
    if suite_srv_dir:
        suite_srv_dir = suite_srv_dir.format(home=tmp_path)
        makedirs(suite_srv_dir, exist_ok=True)
        if readlink and readlink != OSError:
            readlink = readlink.format(home=tmp_path)
            makedirs(readlink, exist_ok=True)
            source_link = os.path.join(
                suite_srv_dir, SuiteSrvFilesManager.FILE_BASE_SOURCE
            )
            os.symlink(readlink, source_link)
    if expected_symlink:
        expected_symlink = expected_symlink.format(home=tmp_path)
    mock_os_symlink = mock.Mock()
    monkeypatch.setattr('cylc.suite_srv_files_mgr.os.symlink', mock_os_symlink)
    suite_srv_files_mgr = SuiteSrvFilesManager()
    suite_srv_files_mgr.get_suite_srv_dir = mock.MagicMock(
        return_value=suite_srv_dir
    )
    # --- Test ---
    if e_expected is None:
        reg = suite_srv_files_mgr.register(reg, source, redirect)
        assert expected == reg
        if mock_os_symlink.call_count > 0:
            # first argument, of the first call
            arg0 = mock_os_symlink.call_args[0][0]
            assert arg0 == expected_symlink
    else:
        with pytest.raises(e_expected) as excinfo:
            suite_srv_files_mgr.register(reg, source, redirect)
        if e_message is not None:
            assert e_message in str(excinfo.value)


@pytest.mark.parametrize(
    'version, expected_err',
    [
        ('6.11.3', None),
        ('7.8.8-26-g03abf-dirty', None),
        ('8.0.0', SuiteCylcVersionError),
        ('8.0b2.dev', SuiteCylcVersionError),
        ('9', SuiteCylcVersionError),
        ('foo', SuiteServiceFileError)
    ]
)
def test_check_cylc_version(version, expected_err):
    if expected_err:
        with pytest.raises(expected_err):
            SuiteSrvFilesManager.check_cylc_version(version)
    else:
        SuiteSrvFilesManager.check_cylc_version(version)
