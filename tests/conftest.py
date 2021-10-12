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

import re
from shutil import rmtree
from typing import List, Optional, Tuple

import pytest

from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.parsec.config import ParsecConfig


@pytest.fixture
def mock_glbl_cfg(tmp_path, monkeypatch):
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
    def _mock(pypath, global_config):
        nonlocal tmp_path, monkeypatch
        global_config_path = tmp_path / 'global.cylc'
        global_config_path.write_text(global_config)
        glbl_cfg = ParsecConfig(SPEC)
        glbl_cfg.loadcfg(global_config_path)

        def _inner(cached=False):
            nonlocal glbl_cfg
            return glbl_cfg

        monkeypatch.setattr(pypath, _inner)

    yield _mock
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
    """
    def _log_filter(
        log: pytest.LogCaptureFixture,
        name: Optional[str] = None,
        level: Optional[int] = None,
        contains: Optional[str] = None,
        regex: Optional[str] = None
    ) -> List[Tuple[str, int, str]]:
        return [
            (log_name, log_level, log_message)
            for log_name, log_level, log_message in log.record_tuples
            if (name is None or name == log_name)
            and (level is None or level == log_level)
            and (contains is None or contains in log_message)
            and (regex is None or re.match(regex, log_message))
        ]
    return _log_filter
