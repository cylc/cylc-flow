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

import unittest

from unittest import mock

from cylc.flow import suite_files
from cylc.flow.exceptions import SuiteServiceFileError


def get_register_test_cases():
    """Test cases for suite_files.register function."""
    return [
        # 1 no parameters provided, current directory is not a symlink,
        # and contains a valid suite.rc
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
        # and contains a valid suite.rc
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
        # 3 suite name and directory location of suite.rc provided,
        # current directory is not a symlink, and contains a valid suite.rc
        ("suite3",  # reg
         "/home/user/cylc-run/suite3/suite.rc",  # source
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
        # 4 suite name and directory location of suite.rc provided,
        # current directory is not a symlink, but the suite.rc does not
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
         "no suite.rc"  # expected part of exception message
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
         "/home/user/cylc-run/suite6/suite.rc",  # source
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
         "/home/user/cylc-run/suite7/suite.rc",  # source
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
         "/home/user/cylc-run/suite8/suite.rc",  # source
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
         "can not start with: ., -"  # expected part of exception message
         )
    ]


class TestSuiteFiles(unittest.TestCase):

    @mock.patch('os.unlink')
    @mock.patch('os.makedirs')
    @mock.patch('os.symlink')
    @mock.patch('os.readlink')
    @mock.patch('os.path.isfile')
    @mock.patch('os.path.isabs')
    @mock.patch('os.getcwd')
    @mock.patch('os.path.abspath')
    @mock.patch('cylc.flow.suite_files.get_suite_srv_dir')
    def test_register(
            self,
            mocked_get_suite_srv_dir,
            mocked_abspath,
            mocked_getcwd,
            mocked_isabs,
            mocked_isfile,
            mocked_readlink,
            mocked_symlink,
            mocked_makedirs,
            mocked_unlink
    ):
        """Test the register function."""
        def mkdirs_standin(_, exist_ok=False):
            return True

        mocked_abspath.side_effect = lambda x: x

        for reg, source, redirect, cwd, isabs, isfile, \
            suite_srv_dir, readlink, expected_symlink, \
            expected, e_expected, e_message \
                in get_register_test_cases():
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
                self.assertEqual(expected, reg)
                if mocked_symlink.call_count > 0:
                    # first argument, of the first call
                    arg0 = mocked_symlink.call_args[0][0]
                    self.assertEqual(expected_symlink, arg0)
            else:
                with self.assertRaises(e_expected) as cm:
                    suite_files.register(reg, source, redirect)
                if e_message is not None:
                    the_exception = cm.exception
                    self.assertTrue(e_message in str(the_exception),
                                    str(the_exception))


if __name__ == '__main__':
    unittest.main()
