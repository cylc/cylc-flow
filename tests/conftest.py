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

from pathlib import Path
import re
from shutil import rmtree
from typing import List, Optional, Tuple

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.validate import cylc_config_validate


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
        nonlocal tmp_path, monkeypatch
        global_config_path = tmp_path / 'global.cylc'
        global_config_path.write_text(global_config)
        glbl_cfg = ParsecConfig(SPEC, validator=cylc_config_validate)
        glbl_cfg.loadcfg(global_config_path)

        def _inner(cached=False):
            nonlocal glbl_cfg
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    yield _mock_glbl_cfg
    rmtree(tmp_path)


@pytest.fixture
def log_filter():
    """Filter caplog record_tuples.

    Args:
        log: The caplog instance.
        name: Filter out records if they don't match this logger name.
        level: Filter out records if they aren't at this logging level.
        contains: Filter out records if this string is not in the message.
        regex: Filter out records if the message doesn't match this regex.
        exact_match: Filter out records if the message does not exactly match
            this string.
    """
    def _log_filter(
        log: pytest.LogCaptureFixture,
        name: Optional[str] = None,
        level: Optional[int] = None,
        contains: Optional[str] = None,
        regex: Optional[str] = None,
        exact_match: Optional[str] = None,
    ) -> List[Tuple[str, int, str]]:
        return [
            (log_name, log_level, log_message)
            for log_name, log_level, log_message in log.record_tuples
            if (name is None or name == log_name)
            and (level is None or level == log_level)
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
        substitute_function:
            An optional function to replace it with, otherwise the captured
            function will return None.

    Returns:
        [(args: Tuple, kwargs: Dict), ...]

    Example:
        def test_something(capcall):
            capsys = capcall('sys.exit')
            sys.exit(1)
            assert capsys == [(1,), {}]

    """

    def _capcall(function_string, substitute_function=None):
        calls = []

        def _call(*args, **kwargs):
            nonlocal calls
            nonlocal substitute_function
            calls.append((args, kwargs))
            if substitute_function:
                return substitute_function(*args, **kwargs)

        monkeypatch.setattr(function_string, _call)
        return calls

    return _capcall
