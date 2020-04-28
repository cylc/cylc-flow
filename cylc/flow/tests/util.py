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

import os
import pytest

from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase
from unittest.mock import patch, MagicMock

from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.config import SuiteConfig
from cylc.flow.job_pool import JobPool
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.scheduler import Scheduler
from cylc.flow.suite_db_mgr import SuiteDatabaseManager
from cylc.flow.task_pool import TaskPool
from cylc.flow.task_proxy import TaskProxy

"""Set of utility methods and classes for writing tests for Cylc."""


class CylcWorkflowTestCase(TestCase):
    """A TestCase that loads simulates a real Cylc workflow.

    Attributes:
        suite_name (str): workflow name
        suiterc (str): suite.rc content
        workflow_directory (Path): base directory for the workflow
        private_database_directory (Path): sqlite private DB directory
        public_database_directory (Path): sqlite public DB directory
        scheduler (MagicMock): mocked object to simulate the Scheduler
        suite_config (SuiteConfig): suite configuration object
        owner (str): suite owner, defaults to 'cylcuser'
        host (str): suite host, defaults to 'localhost'
        port (int): suite port, defaults to 42000
        task_pool (TaskPool): pool of tasks
        suite_db_mgr (SuiteDatabaseManager): suite database manager
    """

    suite_name: str = None
    suiterc: str = None

    def __init__(self, *args, **kwargs):
        super(CylcWorkflowTestCase, self).__init__(*args, **kwargs)
        self.workflow_directory = Path(mkdtemp())
        self.private_database_directory = Path(mkdtemp())
        self.public_database_directory = Path(mkdtemp())
        self.scheduler = None
        self.suite_config = None
        self.owner = 'cylcuser'
        self.host = 'localhost'
        self.port = 42000
        self.task_pool = None
        self.suite_db_mgr = None
        self.job_pool = None

    def setUp(self) -> None:
        """Create base objects for the tests."""
        super(CylcWorkflowTestCase, self).setUp()
        self.init()

    def tearDown(self) -> None:
        """Clean up used resources."""
        if self.workflow_directory:
            rmtree(self.workflow_directory)
        if self.private_database_directory:
            rmtree(self.private_database_directory)
        if self.public_database_directory:
            rmtree(self.public_database_directory)

    @patch('cylc.flow.scheduler.Scheduler')
    def init(self, mocked_scheduler: Scheduler) -> None:
        """
        Prepare common objects for a Cylc Workflow test case.

        Args:
            mocked_scheduler (Scheduler):
        """
        if not self.suite_name:
            raise ValueError('You must provide a suite name')
        if not self.suiterc:
            raise ValueError('You must provide a suiterc content')

        # SuiteConfig
        self.suite_config = create_suite_config(
            self.workflow_directory, self.suite_name, self.suiterc)
        assert self.suite_config

        # Scheduler
        self.scheduler = mocked_scheduler
        self.scheduler.server = MagicMock()
        self.scheduler.suite = self.suite_name
        self.scheduler.owner = self.owner
        self.scheduler.config = self.suite_config
        self.scheduler.host = self.host
        self.scheduler.port = self.port
        self.scheduler.suite_log_dir = ''

        # SuiteDatabaseManager and workflow database
        self.suite_db_mgr = SuiteDatabaseManager(
            pri_d=self.private_database_directory.resolve(),
            pub_d=self.public_database_directory.resolve())
        self.suite_db_mgr.on_suite_start(is_restart=False)

        # JobPool
        self.job_pool = JobPool(self.scheduler)
        self.scheduler.job_pool = self.job_pool

        # TaskPool
        self.task_pool = TaskPool(
            self.suite_config,
            suite_db_mgr=self.suite_db_mgr,
            task_events_mgr=None,
            job_pool=self.job_pool)
        self.scheduler.pool = self.task_pool


def create_suite_config(workflow_directory: Path, suite_name: str,
                        suiterc_content: str) -> SuiteConfig:
    """Create a SuiteConfig object from a suiterc content.

    Args:
        workflow_directory (Path): workflow base directory
        suite_name (str): suite name
        suiterc_content (str): suiterc content
    """
    suite_rc = Path(workflow_directory, "suite.rc")
    with suite_rc.open(mode="w") as f:
        f.write(suiterc_content)
        f.flush()
        return SuiteConfig(suite=suite_name, fpath=f.name)


def create_task_proxy(task_name: str, suite_config: SuiteConfig,
                      is_startup=False) -> TaskProxy:
    """Create a Task Proxy based on a TaskDef loaded from the SuiteConfig.

    Args:
        task_name (str): task name
        suite_config (SuiteConfig): SuiteConfig object that holds task
            definitions
        is_startup (bool): whether we are starting the workflow or not
    """
    task_def = suite_config.get_taskdef(task_name)
    return TaskProxy(
        tdef=task_def,
        start_point=suite_config.start_point,
        is_startup=is_startup)


@pytest.fixture()
def set_up_globalrc(tmp_path_factory):
    """A Pytest fixture for fiddling globalrc values.

    Creates a globalrc file and modifies CYLC_CONF_PATH to point at it.

    Use for:

    * Functional tests which call out to other scripts.
    * Integration tests which span multiple modules.

    """
    def _inner_func(rc_string):
        tempdir = tmp_path_factory.getbasetemp()
        globalrc = tempdir / 'flow.rc'
        with open(str(globalrc), 'w') as file_handle:
            file_handle.write(rc_string)
        os.environ['CYLC_CONF_PATH'] = str(tempdir)
        return globalrc

    return _inner_func


@pytest.fixture
def mock_glbl_cfg(tmp_path, monkeypatch):
    """A Pytest fixture for fiddling globalrc values.

    Hacks the specified `glbl_cfg` object.

    Use for:

    * Isolated unit tests within one module.

    # TODO: modify Parsec so we can use StringIO rather than a temp file.

    """
    def _mock(pypath, global_rc):
        nonlocal tmp_path, monkeypatch
        tmp_path = tmp_path / 'flow.rc'
        tmp_path.write_text(global_rc)
        glbl_cfg = ParsecConfig(SPEC)
        glbl_cfg.loadcfg(tmp_path)

        def _inner(cached=False):
            nonlocal glbl_cfg
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    return _mock
