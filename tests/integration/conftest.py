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
"""Default fixtures for functional tests."""

import asyncio
from functools import partial
from pathlib import Path
import re
from shutil import rmtree
from time import time
from typing import (
    TYPE_CHECKING,
    List,
    Set,
    Tuple,
    Union,
)

import pytest

from cylc.flow.config import WorkflowConfig
from cylc.flow.id import Tokens
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.option_parsers import Options
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.run_modes import RunMode
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.scripts.install import (
    get_option_parser as install_gop,
    install as cylc_install,
)
from cylc.flow.scripts.show import (
    ShowOptions,
    prereqs_and_outputs_query,
)
from cylc.flow.scripts.validate import ValidateOptions
from cylc.flow.task_state import (
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUCCEEDED,
)
from cylc.flow.util import serialise_set
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.workflow_files import infer_latest_run_from_id
from cylc.flow.workflow_status import StopMode

from .utils import _rm_if_empty
from .utils.flow_tools import (
    _make_flow,
    _make_scheduler,
    _make_src_flow,
    _run_flow,
    _start_flow,
)


if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler
    from cylc.flow.task_proxy import TaskProxy


InstallOpts = Options(install_gop())


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose the result of tests to their fixtures.

    This will add a variable to the "node" object which differs depending on
    the scope of the test.

    scope=function
        `_function_outcome` will be set to the result of the test function.
    scope=module
        `_module_outcome will be set to a list of all test results in
        the module.

    https://github.com/pytest-dev/pytest/issues/230#issuecomment-402580536

    """
    outcome = yield
    rep = outcome.get_result()

    # scope==function
    item._function_outcome = rep

    # scope==module
    _module_outcomes = getattr(item.module, '_module_outcomes', {})
    _module_outcomes[(item.nodeid, rep.when)] = rep
    item.module._module_outcomes = _module_outcomes


def _pytest_passed(request: pytest.FixtureRequest) -> bool:
    """Returns True if the test(s) a fixture was used in passed."""
    if hasattr(request.node, '_function_outcome'):
        return request.node._function_outcome.outcome in {'passed', 'skipped'}
    return all((
        report.outcome in {'passed', 'skipped'}
        for report in request.node.obj._module_outcomes.values()
    ))


@pytest.fixture(scope='session')
def run_dir():
    """The cylc run directory for this host."""
    path = Path(get_cylc_run_dir())
    path.mkdir(exist_ok=True)
    yield path


@pytest.fixture(scope='session')
def ses_test_dir(request, run_dir):
    """The root run dir for test flows in this test session."""
    timestamp = get_current_time_string(use_basic_format=True)
    uuid = f'cit-{timestamp}'
    path = Path(run_dir, uuid)
    path.mkdir(exist_ok=True)
    yield path
    _rm_if_empty(path)


@pytest.fixture(scope='module')
def mod_test_dir(request, ses_test_dir):
    """The root run dir for test flows in this test module."""
    path = Path(
        ses_test_dir,
        # Shorten path by dropping `integration.` prefix:
        re.sub(r'^integration\.', '', request.module.__name__)
    )
    path.mkdir(exist_ok=True)
    yield path
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=False)
    else:
        # test failed -> remove the test dir if empty
        _rm_if_empty(path)


@pytest.fixture
def test_dir(request, mod_test_dir):
    """The root run dir for test flows in this test function."""
    path = Path(mod_test_dir, request.function.__name__)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    if _pytest_passed(request):
        # test passed -> remove all files
        rmtree(path, ignore_errors=False)
    else:
        # test failed -> remove the test dir if empty
        _rm_if_empty(path)


@pytest.fixture(scope='module')
def mod_flow(run_dir, mod_test_dir):
    """A function for creating module-level flows."""
    yield partial(_make_flow, run_dir, mod_test_dir)


@pytest.fixture
def flow(run_dir, test_dir):
    """A function for creating function-level flows."""
    yield partial(_make_flow, run_dir, test_dir)


@pytest.fixture(scope='module')
def mod_scheduler():
    """Return a Scheduler object for a flow.

    Usage: see scheduler() below
    """
    with _make_scheduler() as _scheduler:
        yield _scheduler


@pytest.fixture
def scheduler():
    """Return a Scheduler object for a flow.

    Args:
        id_ (str): Workflow name.
        **opts (Any): Options to be passed to the Scheduler.
    """
    with _make_scheduler() as _scheduler:
        yield _scheduler


@pytest.fixture(scope='module')
def mod_start():
    """Start a scheduler but don't set it running (module scope)."""
    return partial(_start_flow, None)


@pytest.fixture
def start(caplog: pytest.LogCaptureFixture):
    """Start a scheduler but don't set it running."""
    return partial(_start_flow, caplog)


@pytest.fixture(scope='module')
def mod_run():
    """Start a scheduler and set it running (module scope)."""
    return partial(_run_flow, None)


@pytest.fixture
def run(caplog: pytest.LogCaptureFixture):
    """Start a scheduler and set it running."""
    return partial(_run_flow, caplog)


@pytest.fixture
def one_conf():
    return {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': 'one'
            }
        }
    }


@pytest.fixture(scope='module')
def mod_one_conf():
    return {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': 'one'
            }
        }
    }


@pytest.fixture
def one(one_conf, flow, scheduler):
    """Return a Scheduler for the simple "R1 = one" graph."""
    id_ = flow(one_conf)
    schd = scheduler(id_)
    return schd


@pytest.fixture(scope='module')
def mod_one(mod_one_conf, mod_flow, mod_scheduler):
    id_ = mod_flow(mod_one_conf)
    schd = mod_scheduler(id_)
    return schd


@pytest.fixture(scope='module')
def event_loop():
    """This fixture defines the event loop used for each test.

    The default scoping for this fixture is "function" which means that all
    async fixtures must have "function" scoping.

    Defining `event_loop` as a module scoped fixture opens the door to
    module scoped fixtures but means all tests in a module will run in the same
    event loop. This is fine, it's actually an efficiency win but also
    something to be aware of.

    See: https://github.com/pytest-dev/pytest-asyncio/issues/171

    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # gracefully exit async generators
    loop.run_until_complete(loop.shutdown_asyncgens())
    # cancel any tasks still running in this event loop
    for task in asyncio.all_tasks(loop):
        task.cancel()
    loop.close()


@pytest.fixture
def db_select():
    """Select columns from workflow database.

    Args:
        schd: The Scheduler object for the workflow.
        process_db_queue: Whether to process the scheduler's db queue before
            querying.
        table: The name of the database table to query.
        *columns (optional): The columns to select from the table. To select
            all columns, omit or use '*'.
        **where (optional): Kwargs specifying <column>='<value>' for use in
            WHERE clauses. If more than one specified, they will be chained
            together using an AND operator.
    """

    def _check_columns(table: str, *columns: str) -> None:
        all_columns = [x[0] for x in CylcWorkflowDAO.TABLES_ATTRS[table]]
        for col in columns:
            if col not in all_columns:
                raise ValueError(f"Column '{col}' not in table '{table}'")

    def _inner(
        schd: 'Scheduler',
        process_db_queue: bool,
        table: str,
        *columns: str,
        **where: str
    ) -> List[Tuple[str, ...]]:

        if process_db_queue:
            schd.process_workflow_db_queue()

        if table not in CylcWorkflowDAO.TABLES_ATTRS:
            raise ValueError(f"Table '{table}' not in database")
        if not columns:
            columns = ('*',)
        elif columns != ('*',):
            _check_columns(table, *columns)

        stmt = f'SELECT {",".join(columns)} FROM {table}'
        stmt_args = []
        if where:
            _check_columns(table, *where.keys())
            where_stmt = ' AND '.join([
                f'{col}=?' for col in where.keys()
            ])
            stmt += f' WHERE {where_stmt}'
            stmt_args = list(where.values())

        with schd.workflow_db_mgr.get_pri_dao() as pri_dao:
            return list(pri_dao.connect().execute(stmt, stmt_args))

    return _inner


@pytest.fixture
def gql_query():
    """Execute a GraphQL query given a workflow runtime client."""
    async def _gql_query(
        client: 'WorkflowRuntimeClient', query_str: str
    ) -> object:
        ret = await client.async_request(
            'graphql', {
                'request_string': 'query { ' + query_str + ' }'
            }
        )
        return ret
    return _gql_query


@pytest.fixture
def validate(run_dir):
    """Provides a function for validating workflow configurations.

    Attempts to load the configuration, will raise exceptions if there are
    errors.

    Args:
        id_ - The flow to validate
        kwargs - Arguments to pass to ValidateOptions
    """
    def _validate(id_: Union[str, Path], **kwargs) -> WorkflowConfig:
        id_ = str(id_)
        return WorkflowConfig(
            id_,
            str(Path(run_dir, id_, 'flow.cylc')),
            ValidateOptions(**kwargs)
        )

    return _validate


@pytest.fixture(scope='module')
def mod_validate(run_dir):
    """Provides a function for validating workflow configurations.

    Attempts to load the configuration, will raise exceptions if there are
    errors.

    Args:
        id_ - The flow to validate
        kwargs - Arguments to pass to ValidateOptions
    """
    def _validate(id_: Union[str, Path], **kwargs) -> WorkflowConfig:
        id_ = str(id_)
        return WorkflowConfig(
            id_,
            str(Path(run_dir, id_, 'flow.cylc')),
            ValidateOptions(**kwargs)
        )

    return _validate


@pytest.fixture
def capture_submission():
    """Suppress job submission and capture submitted tasks.

    Provides a function to run on a Scheduler *whilst started*, use like so:

    async with start(schd):
        submitted_tasks = capture_submission(schd)

    or:

    async with run(schd):
        submitted_tasks = capture_submission(schd)

    """

    def _disable_submission(schd: 'Scheduler') -> 'Set[TaskProxy]':
        submitted_tasks: 'Set[TaskProxy]' = set()

        def _submit_task_jobs(itasks):
            for itask in itasks:
                itask.state_reset(TASK_STATUS_SUBMITTED)
            submitted_tasks.update(itasks)
            return itasks

        schd.submit_task_jobs = _submit_task_jobs  # type: ignore
        return submitted_tasks

    return _disable_submission


@pytest.fixture
def capture_polling():
    """Suppress job polling and capture polled tasks.

    Provides a function to run on a started Scheduler.

    async with start(schd):
        polled_tasks = capture_polling(schd)

    or:

    async with run(schd):
        polled_tasks = capture_polling(schd)

    """
    def _disable_polling(schd: 'Scheduler') -> 'Set[TaskProxy]':
        polled_tasks: 'Set[TaskProxy]' = set()

        def run_job_cmd(_, itasks, *__, **___):
            polled_tasks.update(itasks)
            return itasks

        schd.task_job_mgr._run_job_cmd = run_job_cmd  # type: ignore
        return polled_tasks

    return _disable_polling


@pytest.fixture(scope='module')
def mod_workflow_source(mod_flow, tmp_path_factory):
    """Create a workflow source directory.

    Args:
        cfg: Can be passed a config dictionary.

    Yields:
        Path to source directory.
    """
    def _inner(cfg):
        src_dir = _make_src_flow(tmp_path_factory.getbasetemp(), cfg)
        return src_dir
    yield _inner


@pytest.fixture
def workflow_source(mod_flow, tmp_path):
    """Create a workflow source directory.

    Args:
        cfg: Can be passed a config dictionary.

    Yields:
        Path to source directory.
    """
    def _inner(cfg):
        src_dir = _make_src_flow(tmp_path, cfg)
        return src_dir
    yield _inner


@pytest.fixture
def install(test_dir, run_dir):
    """Install a workflow from source

    Args:
        (Actually args for _inner, but what the fixture appears to take to
        the user)
        source: Directory containing the source.
        **kwargs: Options for cylc install.

    Returns:
        Workflow id, including run directory.
    """
    async def _inner(source, **kwargs):
        opts = InstallOpts(**kwargs)
        # Note we append the source.name to the string rather than creating
        # a subfolder because the extra layer of directories would exceed
        # Cylc install's default limit.
        opts.workflow_name = (
            f'{str(test_dir.relative_to(run_dir))}.{source.name}')
        workflow_id, _ = await cylc_install(opts, str(source))
        workflow_id = infer_latest_run_from_id(workflow_id)
        return workflow_id
    yield _inner


@pytest.fixture
def reflog():
    """Integration test version of the --reflog CLI option.

    This returns a set which captures task triggers.

    Note, you'll need to call this on the scheduler *after* you have started
    it.

    N.B. Trigger order is not stable; using a set ensures that tests check
    trigger logic rather than binding to specific trigger order which could
    change in the future, breaking the test.

    Args:
        schd:
            The scheduler to capture triggering information for.
        flow_nums:
            If True, the flow numbers of the task being triggered will be added
            to the end of each entry.

    Returns:
        tuple

        (task, triggers):
            If flow_nums == False
        (task, flow_nums, triggers):
            If flow_nums == True

        task:
            The [relative] task ID e.g. "1/a".
        flow_nums:
            The serialised flow nums e.g. ["1"].
        triggers:
            Sorted tuple of the trigger IDs, e.g. ("1/a", "2/b").

    """

    def _reflog(schd: 'Scheduler', flow_nums: bool = False) -> Set[tuple]:
        submit_task_jobs = schd.submit_task_jobs
        triggers = set()

        def _submit_task_jobs(*args, **kwargs):
            itasks = submit_task_jobs(*args, **kwargs)
            for itask in itasks:
                deps = tuple(sorted(itask.state.get_resolved_dependencies()))
                if flow_nums:
                    triggers.add(
                        (
                            itask.identity,
                            serialise_set(itask.flow_nums),
                            deps or None,
                        )
                    )
                else:
                    triggers.add((itask.identity, deps or None))
            return itasks

        schd.submit_task_jobs = _submit_task_jobs

        return triggers

    return _reflog


async def _complete(
    schd: 'Scheduler',
    *wait_tokens: Union[Tokens, str],
    stop_mode=StopMode.AUTO,
    timeout: int = 60,
    allow_paused: bool = False,
) -> None:
    """Wait for the workflow, or tasks within it to complete.

    Args:
        schd:
            The scheduler to await.
        wait_tokens:
            If specified, this will wait for the tasks represented by these
            tokens to be marked as completed by the task pool. Can use
            relative task ids as strings (e.g. '1/a') rather than tokens for
            convenience.
        stop_mode:
            If tokens_list is not provided, this will wait for the scheduler
            to be shutdown with the specified mode (default = AUTO, i.e.
            workflow completed normally).
        timeout:
            Max time to wait for the condition to be met.

            Note, if you need to increase this, you might want to rethink your
            test.

            Note, use this timeout rather than wrapping the complete call with
            async.timeout (handles shutdown logic more cleanly).
        allow_paused:
            This function will raise an Exception if the scheduler is paused
            (because this usually means the sepecified tasks cannot complete)
            unless allow_paused==True.

    Raises:
        AssertionError: In the event the scheduler shut down or the operation
            timed out.

    """
    if schd.is_paused and not allow_paused:
        raise Exception("Cannot wait for completion of a paused scheduler")

    start_time = time()

    tokens_list: List[Tokens] = []
    for tokens in wait_tokens:
        if isinstance(tokens, str):
            tokens = Tokens(tokens, relative=True)
        tokens_list.append(tokens.task)

    # capture task completion
    remove_if_complete = schd.pool.remove_if_complete

    def _remove_if_complete(itask, output=None):
        ret = remove_if_complete(itask)
        if ret and itask.tokens.task in tokens_list:
            tokens_list.remove(itask.tokens.task)
        return ret

    # capture workflow shutdown request
    set_stop = schd._set_stop
    stop_requested = False

    def _set_stop(mode=None):
        nonlocal stop_requested
        if mode == stop_mode:
            stop_requested = True
            return set_stop(mode)
        else:
            set_stop(mode)
            raise Exception(f'Workflow bailed with stop mode = {mode}')

    # determine the completion condition
    def done():
        if wait_tokens:
            if not tokens_list:
                return True
            if not schd.contact_data:
                raise AssertionError(
                    "Scheduler shut down before tasks completed: " +
                    ", ".join(map(str, tokens_list))
                )
            return False
        # otherwise wait for the scheduler to shut down
        return stop_requested or not schd.contact_data

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(schd.pool, 'remove_if_complete', _remove_if_complete)
        mp.setattr(schd, '_set_stop', _set_stop)

        # wait for the condition to be met
        while not done():
            # allow the main loop to advance
            await asyncio.sleep(0)
            if (time() - start_time) > timeout:
                msg = "Timeout waiting for "
                if wait_tokens:
                    msg += ", ".join(map(str, tokens_list))
                else:
                    msg += "workflow to shut down"
                raise AssertionError(msg)


@pytest.fixture
def complete():
    return _complete


@pytest.fixture(scope='module')
def mod_complete():
    return _complete


@pytest.fixture
def reftest(run, reflog, complete):
    """Fixture that runs a simple reftest.

    Combines the `reflog` and `complete` fixtures.
    """
    async def _reftest(
        schd: 'Scheduler',
        flow_nums: bool = False,
    ) -> Set[tuple]:
        async with run(schd):
            triggers = reflog(schd, flow_nums)
            await complete(schd)

        return triggers

    return _reftest


@pytest.fixture
def cylc_show():
    """Fixture that runs `cylc show` on a scheduler, returning JSON object."""

    async def _cylc_show(schd: 'Scheduler', *task_ids: str) -> dict:
        pclient = WorkflowRuntimeClient(schd.workflow)
        await schd.update_data_structure()
        json_filter: dict = {}
        await prereqs_and_outputs_query(
            schd.id,
            [Tokens(id_, relative=True) for id_ in task_ids],
            pclient,
            ShowOptions(json=True),
            json_filter,
        )
        return json_filter

    return _cylc_show


@pytest.fixture
def capture_live_submissions(capcall, monkeypatch):
    """Capture live submission attempts.

    This prevents real jobs from being submitted to the system.

    If you call this fixture from a test, it will return a set of tasks that
    would have been submitted had this fixture not been used.
    """
    def fake_submit(self, itasks, *_):
        self.submit_nonlive_task_jobs(itasks, RunMode.SIMULATION)
        for itask in itasks:
            for status in (TASK_STATUS_SUBMITTED, TASK_STATUS_SUCCEEDED):
                self.task_events_mgr.process_message(
                    itask,
                    'INFO',
                    status,
                    '2000-01-01T00:00:00Z',
                    '(received)',
                )
        return itasks

    # suppress and capture live submissions
    submit_live_calls = capcall(
        'cylc.flow.task_job_mgr.TaskJobManager.submit_livelike_task_jobs',
        fake_submit)

    def get_submissions():
        return {
            itask.identity
            for ((_self, itasks, *_), _kwargs) in submit_live_calls
            for itask in itasks
        }

    return get_submissions
