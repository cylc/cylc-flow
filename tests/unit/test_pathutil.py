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
"""Tests for "cylc.flow.pathutil"."""

from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch, MagicMock, call

import pytest
import os
import logging

from cylc.flow.exceptions import WorkflowFilesError

from cylc.flow.pathutil import (
    get_dirs_to_symlink,
    get_remote_suite_run_dir,
    get_remote_suite_run_job_dir,
    get_remote_suite_work_dir,
    get_suite_run_dir,
    get_suite_run_job_dir,
    get_suite_run_log_dir,
    get_suite_run_log_name,
    get_suite_run_pub_db_name,
    get_suite_run_config_log_dir,
    get_suite_run_share_dir,
    get_suite_run_work_dir,
    get_suite_test_log_name, make_localhost_symlinks,
    make_suite_run_tree, make_symlink,
)


@pytest.mark.parametrize(
    'func, extra_args, expected',
    [
        (get_remote_suite_run_dir, (), "$HOME/annapurna/foo"),
        (
            get_remote_suite_run_dir,
            ("comes", "true"),
            "$HOME/annapurna/foo/comes/true",
        ),
        (
            get_remote_suite_run_job_dir,
            (),
            "$HOME/annapurna/foo/log/job"),
        (
            get_remote_suite_run_job_dir,
            ("comes", "true"),
            "$HOME/annapurna/foo/log/job/comes/true",
        ),
        (get_remote_suite_work_dir, (), "$HOME/K2/foo"),
        (
            get_remote_suite_work_dir,
            ("comes", "true"),
            "$HOME/K2/foo/comes/true",
        ),
    ]
)
def test_get_remote_suite_run_dirs(
    func, extra_args, expected
):
    """
    Tests for get_remote_suite_run_[|job|work]_dir
    Pick a unusual cylc dir names to ensure not picking up system settings
    Pick different names for run and work dir to ensure that the test
    isn't passing by accident.
    """
    platform = {
        'run directory': '$HOME/annapurna',
        'work directory': '$HOME/K2',
    }
    if extra_args:
        result = func(platform, 'foo', *extra_args)
    else:
        result = func(platform, 'foo')
    assert result == expected


class TestPathutil(TestCase):
    """Tests for functions in "cylc.flow.pathutil".

    TODO: Refactor these tests using `pytest.mark.parametrize` so
          that the tester can more easily see which function ha
          failed.
    """
    @patch('cylc.flow.pathutil.get_platform')
    def test_get_suite_run_dirs(self, mocked_platform):
        """Usage of get_suite_run_*dir."""
        homedir = os.getenv("HOME")
        mocked = MagicMock()
        mocked_platform.return_value = {
            'run directory': '$HOME/cylc-run',
            'work directory': '$HOME/cylc-run'
        }
        # func = get_remote_* function to test
        # tail1 = expected tail of return value from configuration
        # args = extra *args
        # tail2 = expected tail of return value from extra args
        for func, tail1 in (
            (get_suite_run_dir, ''),
            (get_suite_run_job_dir, '/log/job'),
            (get_suite_run_log_dir, '/log/suite'),
            (get_suite_run_config_log_dir, '/log/flow-config'),
            (get_suite_run_share_dir, '/share'),
            (get_suite_run_work_dir, '/work'),
        ):
            for args, tail2 in (
                ((), ''),
                (('comes', 'true'), '/comes/true'),
            ):
                expected_result =\
                    f'{homedir}/cylc-run/my-workflow/dream{tail1}{tail2}'
                assert func('my-workflow/dream', *args) == expected_result
                mocked_platform.assert_called_with()
                mocked.get_host_item.reset_mock()

    @patch('cylc.flow.pathutil.get_platform')
    def test_get_suite_run_names(self, mocked_platform):
        """Usage of get_suite_run_*name."""
        homedir = os.getenv("HOME")
        mocked = MagicMock()
        mocked_platform.return_value = {
            'run directory': '$HOME/cylc-run',
            'work directory': '$HOME/cylc-run'
        }
        # func = get_remote_* function to test
        # cfg = configuration used in mocked global configuration
        # tail1 = expected tail of return value from configuration
        for func, cfg, tail1 in (
            (get_suite_run_log_name, 'run directory', '/log/suite/log'),
            (get_suite_run_pub_db_name, 'run directory', '/log/db'),
            (get_suite_test_log_name, 'run directory',
             '/log/suite/reftest.log'),
        ):
            assert (
                func('my-suite/dream') ==
                f'{homedir}/cylc-run/my-suite/dream{tail1}'
            )
            mocked_platform.assert_called_with()
            mocked.get_host_item.reset_mock()


@pytest.mark.parametrize(
    'subdir',
    [
        '',
        '/log/suite',
        '/log/job',
        '/log/flow-config',
        '/share',
        '/work'
    ]
)
def test_make_suite_run_tree(caplog, tmpdir, mock_glbl_cfg, subdir):
    glbl_conf_str = f'''
        run directory rolling archive length = 1
        [platforms]
            [[localhost]]
                run directory = {tmpdir}
                work directory = {tmpdir}
        '''

    mock_glbl_cfg('cylc.flow.platforms.glbl_cfg', glbl_conf_str)
    mock_glbl_cfg('cylc.flow.pathutil.glbl_cfg', glbl_conf_str)

    caplog.set_level(logging.DEBUG)
    # running the logic three times to ensure that the rolling
    # archive logic is covered.
    for i in range(3):
        make_suite_run_tree('my-workflow')

    # Check that directories have been created
    assert (tmpdir / 'my-workflow' / subdir).isdir() is True
    # ...and 1 rolling archive ...
    assert (tmpdir / 'my-workflow.1' / subdir).isdir() is True
    # ... but not 2.
    assert (tmpdir / 'my-workflow.2' / subdir).isdir() is False


@pytest.mark.parametrize(
    'suite, install_target, mocked_glbl_cfg, output',
    [
        (  # basic
            'suite1', 'install_target_1',
            '''[symlink dirs]
            [[install_target_1]]
                run = $DEE
                work = $DAH
                log = $DUH
                share = $DOH
                share/cycle = $DAH''', {
                'run': '$DEE/cylc-run/suite1',
                'work': '$DAH/cylc-run/suite1/work',
                'log': '$DUH/cylc-run/suite1/log',
                'share': '$DOH/cylc-run/suite1/share',
                'share/cycle': '$DAH/cylc-run/suite1/share/cycle'
            }),
        (  # remove nested run symlinks
            'suite2', 'install_target_2',
            '''
        [symlink dirs]
            [[install_target_2]]
                run = $DEE
                work = $DAH
                log = $DEE
                share = $DOH
                share/cycle = $DAH

        ''', {
                'run': '$DEE/cylc-run/suite2',
                'work': '$DAH/cylc-run/suite2/work',
                'share': '$DOH/cylc-run/suite2/share',
                'share/cycle': '$DAH/cylc-run/suite2/share/cycle'
            }),
        (  # remove only nested run symlinks
            'suite3', 'install_target_3', '''
        [symlink dirs]
            [[install_target_3]]
                run = $DOH
                log = $DEE
                share = $DEE
        ''', {
                'run': '$DOH/cylc-run/suite3',
                'log': '$DEE/cylc-run/suite3/log',
                'share': '$DEE/cylc-run/suite3/share'})
    ])
def test_get_dirs_to_symlink(
        suite, install_target, mocked_glbl_cfg, output, mock_glbl_cfg):
    mock_glbl_cfg('cylc.flow.pathutil.glbl_cfg', mocked_glbl_cfg)
    dirs = get_dirs_to_symlink(install_target, suite)
    assert dirs == output
    
@patch('os.path.expandvars')
@patch('cylc.flow.pathutil.get_suite_run_dir')
@patch('cylc.flow.pathutil.make_symlink')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_make_localhost_symlinks_calls_make_symlink_for_each_key_value_dir(
        mocked_dirs_to_symlink,
        mocked_make_symlink,
        mocked_get_suite_run_dir, mocked_expandvars):

    mocked_dirs_to_symlink.return_value = {
        'run': '$DOH/suite3',
        'log': '$DEE/suite3/log',
        'share': '$DEE/suite3/share'}
    mocked_get_suite_run_dir.return_value = "rund"
    mocked_expandvars.return_value = "expanded"

    make_localhost_symlinks('suite')

    mocked_make_symlink.assert_has_calls([
        call('expanded', 'rund'),
        call('expanded', 'rund/log'),
        call('expanded', 'rund/share')
    ])


@patch('os.path.expandvars')
@patch('cylc.flow.pathutil.get_suite_run_dir')
@patch('cylc.flow.pathutil.make_symlink')
@patch('cylc.flow.pathutil.get_dirs_to_symlink')
def test_incorrect_environment_variables_raise_error(
        mocked_dirs_to_symlink,
        mocked_make_symlink,
        mocked_get_suite_run_dir, mocked_expandvars):
    mocked_dirs_to_symlink.return_value = {'run': '$DOH/test_workflow'}
    mocked_get_suite_run_dir.return_value = "rund"
    mocked_expandvars.return_value = "$doh"

    with pytest.raises(WorkflowFilesError, match=r"Unable to create symlink"
                       r" to \$doh. Please check configuration."):
        make_localhost_symlinks('test_workflow')

if __name__ == '__main__':
    from unittest import main
    main()
