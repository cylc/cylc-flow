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

import logging
import re
from pathlib import Path
from shutil import rmtree
from typing import Callable, List, Optional, Tuple
import time

import pytest

from cylc.flow import LOG, flags
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.graphnode import GraphNodeParser
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.validate import cylc_config_validate


@pytest.fixture(autouse=True)
def before_each():
    """Reset global state before every test."""
    flags.verbosity = 0
    flags.cylc7_back_compat = False
    LOG.setLevel(logging.NOTSET)
    # Reset graph node parser singleton:
    GraphNodeParser.get_inst().clear()


@pytest.fixture(scope='module')
def mod_monkeypatch():
    """A module-scoped version of the monkeypatch fixture."""
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture
def mock_glbl_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A Pytest fixture for fiddling global config values.

    * Hacks the specified `glbl_cfg` object.
    * Can be called multiple times within a test function.

    Args:
        pypath (str):
            The python-like path to the global configuation object you want
            to fiddle.
            E.G. if you want to hack the `glbl_cfg` in
            `cylc.flow.scheduler` you would provide
            `cylc.flow.scheduler.glbl_cfg`
        global_config (str):
            The globlal configuration as a multi-line string.

    Example:
        Change the value of `UTC mode` in the global config as seen from
        `the scheduler` module.

        def test_something(mock_glbl_cfg):
            mock_glbl_cfg(
                'cylc.flow.scheduler.glbl_cfg',
                '''
                    [scheduler]
                        UTC mode = True
                '''
            )

    """
    # TODO: modify Parsec so we can use StringIO rather than a temp file.
    def _mock_glbl_cfg(pypath: str, global_config: str) -> None:
        global_config_path = tmp_path / 'global.cylc'
        global_config_path.write_text(global_config)
        glbl_cfg = ParsecConfig(SPEC, validator=cylc_config_validate)
        glbl_cfg.loadcfg(global_config_path)

        def _inner(cached=False):
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    yield _mock_glbl_cfg
    rmtree(tmp_path)


@pytest.fixture
def log_filter(caplog: pytest.LogCaptureFixture):
    """Filter caplog record_tuples (also discarding the log name entry).

    Args:
        level: Filter out records if they aren't at this logging level.
        contains: Filter out records if this string is not in the message.
        regex: Filter out records if the message doesn't match this regex.
        exact_match: Filter out records if the message does not exactly match
            this string.
        log: A caplog instance.
    """
    def _log_filter(
        level: Optional[int] = None,
        contains: Optional[str] = None,
        regex: Optional[str] = None,
        exact_match: Optional[str] = None,
        log: Optional[pytest.LogCaptureFixture] = None
    ) -> List[Tuple[int, str]]:
        if log is None:
            log = caplog
        return [
            (log_level, log_message)
            for _, log_level, log_message in log.record_tuples
            if (level is None or level == log_level)
            and (contains is None or contains in log_message)
            and (regex is None or re.search(regex, log_message))
            and (exact_match is None or exact_match == log_message)
        ]
    return _log_filter


@pytest.fixture
def log_scan():
    """Ensure log messages appear in the correct order.

    TRY TO AVOID DOING THIS!

    If you are trying to test a sequence of events you are likely better off
    doing this a different way (e.g. mock the functions you are interested in
    and test the call arguments/returns later).

    However, there are some occasions where this might be necessary, e.g.
    testing a monolithic synchronous function.

    Args:
        log: The caplog fixture.
        items: Iterable of string messages to compare. All are tested
            by "contains" i.e. "item in string".

    """
    def _log_scan(log, items):
        records = iter(log.records)
        record = next(records)
        for item in items:
            while item not in record.message:
                try:
                    record = next(records)
                except StopIteration:
                    raise Exception(f'Reached end of log looking for: {item}')

    return _log_scan


@pytest.fixture(scope='session')
def port_range():
    return glbl_cfg().get(['scheduler', 'run hosts', 'ports'])


@pytest.fixture
def capcall(monkeypatch):
    """Capture function calls without running the function.

    Returns a list which is populated with function calls.

    Args:
        function_string:
            The function to replace as it would be specified to
            monkeypatch.setattr.
        mock:
            * If True, the function will be replaced by a "return None".
            * If False, the original function will be run.
            * If a Callable is provided, this will be run in place of the
              original function.

    Returns:
        [(args: Tuple, kwargs: Dict), ...]

    Example:
        def test_something(capcall):
            capsys = capcall('sys.exit')
            sys.exit(1)
            assert capsys == [(1,), {}]

    """

    def _capcall(function_string: str, mock: bool | Callable = True):
        calls = []

        if mock is True:
            fcn = lambda *args, **kwargs: None
        elif mock is False:
            fcn = import_object_from_string(function_string)
        else:
            fcn = mock

        def _call(*args, **kwargs):
            calls.append((args, kwargs))
            return fcn(*args, **kwargs)

        monkeypatch.setattr(function_string, _call)
        return calls

    return _capcall


def import_object_from_string(string):
    """Import a Python object from a string path.

    The path may reference a module, function, class, method, whatever.

    Examples:
        # import a module
        >>> import_object_from_string('os')
        <module 'os' ...>

        # import a function
        >>> import_object_from_string('os.path.walk')
        <function walk at ...>

        # import a constant from a namespace package
        >>> import_object_from_string('cylc.flow.LOG')
        <Logger cylc (WARNING)>

        # import a class
        >>> import_object_from_string('pathlib.Path')
        <class 'pathlib.Path'>

        # import a method
        >>> import_object_from_string('pathlib.Path.exists')
        <function Path.exists ...>

    """
    head = string
    tail = []
    while True:
        try:
            # try and import the thing
            module = __import__(head)
        except ModuleNotFoundError:
            # if it's not something we can import, lop the last item off the
            # end of the string and repeat
            if '.' in head:
                head, _tail = head.rsplit('.', 1)
                tail.append(_tail)
            else:
                # we definitely can't import this
                raise
        else:
            # we managed to import something
            if '(namespace)' in str(module):
                # with namespace packages you have to pull the module out of
                # the package yourself
                for part in head.split('.')[1:]:
                    module = getattr(module, part)
            break

    # extract the requested object from the module (if requested)
    obj = module
    for part in reversed(tail):
        obj = getattr(obj, part)

    return obj


@pytest.fixture
def set_timezone(monkeypatch):
    """Fixture to temporarily set a timezone.

    Will use a very implausible timezone if none is provided.
    """
    def patch(time_zone: str):
        monkeypatch.setenv('TZ', time_zone)
        time.tzset()

    try:
        yield patch
    finally:
        # Reset to the original time zone after the test
        monkeypatch.undo()
        time.tzset()
