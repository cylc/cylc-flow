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

from unittest import TestCase
from unittest.mock import call, patch, MagicMock
import pytest
import os
import cylc.flow.platforms
from cylc.flow.pathutil import (
    get_remote_suite_run_dir,
    get_remote_suite_run_job_dir,
    get_remote_suite_work_dir,
    get_suite_run_dir,
    get_suite_run_job_dir,
    get_suite_run_log_dir,
    get_suite_run_log_name,
    get_suite_run_pub_db_name,
    get_suite_run_rc_dir,
    get_suite_run_share_dir,
    get_suite_run_work_dir,
    get_suite_test_log_name,
    make_suite_run_tree,
)


# TODO - parameterize for all local methods
def test_get_suite_run_dir(monkeypatch):
    monkeypatch.setattr(
        cylc.flow.platforms,
        "forward_lookup", lambda: {'run directory': '$HOME/cylc-run'}
    )
    homedir = os.getenv("HOME")
    assert get_suite_run_dir('joe') == f'{homedir}/cylc-run/joe'


# TODO - parameterize and have work for all remote methods
def test_get_remote_suite_run_dir(monkeypatch):
    platform = {'run directory': '$HOME/cylc-andromeda'}
    result = get_remote_suite_run_dir(platform, 'joe')
    assert result == '$HOME/cylc-andromeda/joe'


class TestPathutil(TestCase):
    """Tests for functions in "cylc.flow.pathutil"."""
    @pytest.mark.skip()
    @patch('cylc.flow.pathutil.glbl_cfg')
    def test_get_remote_suite_run_dirs(self, mocked_glbl_cfg):
        # TODO Fix this for platforms
        """Usage of get_remote_suite_run_*dir."""
        mocked = MagicMock()
        mocked_glbl_cfg.return_value = mocked
        mocked.get_host_item.return_value = '/home/sweet/cylc-run'
        # func = get_remote_* function to test
        # cfg = configuration used in mocked global configuration
        # tail1 = expected tail of return value from configuration
        # args = extra *args
        # tail2 = expected tail of return value from extra args
        for func, cfg, tail1 in (
            (get_remote_suite_run_dir, 'run directory', ''),
            (get_remote_suite_run_job_dir, 'run directory', '/log/job'),
            (get_remote_suite_work_dir, 'work directory', ''),
        ):
            for args, tail2 in (
                ((), ''),
                (('comes', 'true'), '/comes/true'),
            ):
                self.assertEqual(
                    f'/home/sweet/cylc-run/my-suite/dream{tail1}{tail2}',
                    func('myhost', 'myuser', 'my-suite/dream', *args),
                )
                mocked.get_host_item.assert_called_with(
                    cfg, 'myhost', 'myuser')
                mocked.get_host_item.reset_mock()

    @pytest.mark.skip()
    @patch('cylc.flow.pathutil.glbl_cfg')
    def test_get_suite_run_dirs(self, mocked_glbl_cfg):
        """Usage of get_suite_run_*dir."""
        # TODO Fix this for platforms
        mocked = MagicMock()
        mocked_glbl_cfg.return_value = mocked
        mocked.get_host_item.return_value = '/home/sweet/cylc-run'
        # func = get_remote_* function to test
        # cfg = configuration used in mocked global configuration
        # tail1 = expected tail of return value from configuration
        # args = extra *args
        # tail2 = expected tail of return value from extra args
        for func, cfg, tail1 in (
            (get_suite_run_dir, 'run directory', ''),
            (get_suite_run_job_dir, 'run directory', '/log/job'),
            (get_suite_run_log_dir, 'run directory', '/log/suite'),
            (get_suite_run_rc_dir, 'run directory', '/log/suiterc'),
            (get_suite_run_share_dir, 'work directory', '/share'),
            (get_suite_run_work_dir, 'work directory', '/work'),
        ):
            for args, tail2 in (
                ((), ''),
                (('comes', 'true'), '/comes/true'),
            ):
                self.assertEqual(
                    f'/home/sweet/cylc-run/my-suite/dream{tail1}{tail2}',
                    func('my-suite/dream', *args),
                )
                mocked.get_host_item.assert_called_with(cfg)
                mocked.get_host_item.reset_mock()

    # TODO Fix this for platforms
    @pytest.mark.skip()
    @patch('cylc.flow.pathutil.glbl_cfg')
    def test_get_suite_run_names(self, mocked_glbl_cfg):
        """Usage of get_suite_run_*name."""
        mocked = MagicMock()
        mocked_glbl_cfg.return_value = mocked
        mocked.get_host_item.return_value = '/home/sweet/cylc-run'
        # func = get_remote_* function to test
        # cfg = configuration used in mocked global configuration
        # tail1 = expected tail of return value from configuration
        for func, cfg, tail1 in (
            (get_suite_run_log_name, 'run directory', '/log/suite/log'),
            (get_suite_run_pub_db_name, 'run directory', '/log/db'),
            (get_suite_test_log_name, 'run directory',
             '/log/suite/reftest.log'),
        ):
            self.assertEqual(
                f'/home/sweet/cylc-run/my-suite/dream{tail1}',
                func('my-suite/dream'),
            )
            mocked.get_host_item.assert_called_with(cfg)
            mocked.get_host_item.reset_mock()

    # TODO Fix this for platforms
    @pytest.mark.skip()
    @patch('cylc.flow.pathutil.os.makedirs')
    @patch('cylc.flow.pathutil.glbl_cfg')
    def test_make_suite_run_tree(self, mocked_glbl_cfg, mocked_makedirs):
        """Usage of make_suite_run_tree."""
        mocked = MagicMock()
        mocked_glbl_cfg.return_value = mocked
        mocked.get_host_item.return_value = '/home/sweet/cylc-run'
        mocked_cfg = MagicMock()
        mocked_cfg['run directory rolling archive length'] = 0
        mocked.get.return_value = mocked_cfg
        make_suite_run_tree('my-suite/dream')
        self.assertEqual(mocked_makedirs.call_count, 6)
        mocked_makedirs.assert_has_calls((
            call(f'/home/sweet/cylc-run/my-suite/dream{tail}', exist_ok=True)
            for tail in (
                '',
                '/log/suite',
                '/log/job',
                '/log/suiterc',
                '/share',
                '/work',
            )
        ))


if __name__ == '__main__':
    from unittest import main
    main()
