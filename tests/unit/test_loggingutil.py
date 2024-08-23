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
import sys
from io import TextIOWrapper
from pathlib import Path
from time import sleep
from typing import Callable, cast
from unittest import mock

import pytest
from pytest import param

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cfgspec.globalcfg import GlobalConfig
from cylc.flow.loggingutil import (
    CylcLogFormatter,
    RotatingLogFileHandler,
    get_reload_start_number,
    get_sorted_logs_by_time,
    patch_log_level,
    set_timestamps,
)


@pytest.fixture
def rotating_log_file_handler(tmp_path: Path):
    """Fixture to create a RotatingLogFileHandler for testing."""
    log_file = tmp_path / "log"
    log_file.touch()

    handler = cast('RotatingLogFileHandler', None)
    orig_stream = cast('TextIOWrapper', None)

    def inner(
        *args, level: int = logging.INFO, **kwargs
    ) -> RotatingLogFileHandler:
        nonlocal handler, orig_stream
        handler = RotatingLogFileHandler(log_file, *args, **kwargs)
        orig_stream = handler.stream
        # next line is important as pytest can have a "Bad file descriptor"
        # due to a FileHandler with default "a" (pytest tries to r/w).
        handler.mode = "a+"

        # enable the logger
        LOG.setLevel(level)
        LOG.addHandler(handler)

        return handler

    yield inner

    # clean up
    LOG.setLevel(logging.INFO)
    LOG.removeHandler(handler)


@mock.patch("cylc.flow.loggingutil.glbl_cfg")
def test_value_error_raises_system_exit(
    mocked_glbl_cfg, rotating_log_file_handler
):
    """Test that a ValueError when writing to a log stream won't result
    in multiple exceptions (what could lead to infinite loop in some
    occasions. Instead, it **must** raise a SystemExit"""
    # mock objects used when creating the file handler
    mocked = mock.MagicMock()
    mocked_glbl_cfg.return_value = mocked
    mocked.get.return_value = 100
    file_handler = rotating_log_file_handler(level=logging.INFO)

    # Disable raising uncaught exceptions in logging, due to file
    # handler using stdin.fileno. See the following links for more.
    # https://github.com/pytest-dev/pytest/issues/2276 &
    # https://github.com/pytest-dev/pytest/issues/1585
    logging.raiseExceptions = False

    # first message will initialize the stream and the handler
    LOG.info("What could go")

    # here we change the stream of the handler
    file_handler.stream = mock.MagicMock()
    file_handler.stream.seek = mock.MagicMock()
    # in case where
    file_handler.stream.seek.side_effect = ValueError

    with pytest.raises(SystemExit):
        # next call will call the emit method and use the mocked stream
        LOG.info("wrong?!")

    # clean up
    logging.raiseExceptions = True


@pytest.mark.parametrize(
    'dev_info, expect',
    [
        param(
            True,
            (
                '%(asctime)s %(levelname)-2s - [%(module)s:%(lineno)d] - '
                '%(message)s'
            ),
            id='dev_info=True'
        ),
        param(
            False,
            '%(asctime)s %(levelname)-2s - %(message)s',
            id='dev_info=False'
        )
    ]
)
def test_CylcLogFormatter__init__dev_info(dev_info, expect):
    """dev_info switch changes the logging format string."""
    formatter = CylcLogFormatter(dev_info=dev_info)
    assert formatter._fmt == expect


def test_update_log_archive(tmp_run_dir: Callable):
    """Test log archive performs as expected"""
    run_dir = tmp_run_dir('some_workflow')
    log_dir = Path(run_dir / 'log' / 'scheduler')
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir.joinpath('log')
    log_file.touch()
    log_object = RotatingLogFileHandler(
        log_file, no_detach=False, restart_num=0
    )

    for i in range(1, 5):
        (log_dir / f'{i:02d}-start-{i:02d}.log').touch()
    log_object.update_log_archive(2)
    assert list((log_dir.iterdir())).sort() == [
        Path(log_dir / 'log'),
        Path(log_dir / '03-start-03.log'),
        Path(log_dir / '04-start-04.log')].sort()


def test_get_sorted_logs_by_time(tmp_run_dir: Callable):
    run_dir = tmp_run_dir('some_workflow')
    config_log_dir = Path(run_dir / 'log' / 'config')
    config_log_dir.mkdir(exist_ok=True, parents=True)
    for file in ['01-start-01.cylc',
                 '02-start-01.cylc',
                 '03-restart-02.cylc',
                 '04-reload-02.cylc']:
        (config_log_dir / file).touch()
        # Sleep required to ensure modification times are sufficiently
        # different for sort
        sleep(0.1)
    loggies = get_sorted_logs_by_time(config_log_dir, "*.cylc")
    assert loggies == [f'{config_log_dir}/01-start-01.cylc',
                       f'{config_log_dir}/02-start-01.cylc',
                       f'{config_log_dir}/03-restart-02.cylc',
                       f'{config_log_dir}/04-reload-02.cylc']


def test_get_reload_number(tmp_run_dir: Callable):
    run_dir = tmp_run_dir('some_reloaded_workflow')
    config_log_dir = Path(run_dir / 'log' / 'config')
    config_log_dir.mkdir(exist_ok=True, parents=True)
    for file in [
        '01-start-01.cylc',
        '02-reload-01.cylc',
        '03-restart-02.cylc',
        '04-restart-02.cylc'
    ]:
        (config_log_dir / file).touch()
        # Sleeps required to ensure modification times are sufficiently
        # different for sort
        sleep(0.1)
    config_logs = get_sorted_logs_by_time(config_log_dir, "*.cylc")

    assert get_reload_start_number(config_logs) == '02'


def test_get_reload_number_no_logs(tmp_run_dir: Callable):
    run_dir = tmp_run_dir('another_reloaded_workflow')
    config_log_dir = Path(run_dir / 'log' / 'config')
    config_log_dir.mkdir(exist_ok=True, parents=True)
    config_logs = get_sorted_logs_by_time(config_log_dir, "*.cylc")
    assert get_reload_start_number(config_logs) == '01'


def test_set_timestamps(capsys):
    """The enable and disable timstamp methods do what they say"""
    # Setup log handler
    log_handler = logging.StreamHandler(sys.stderr)
    log_handler.setFormatter(CylcLogFormatter())
    LOG.addHandler(log_handler)

    # Log some messages with timestamps on or off:
    LOG.warning('foo')
    set_timestamps(LOG, False)
    LOG.warning('bar')
    set_timestamps(LOG, True)
    LOG.warning('baz')

    # Check 1st and 3rd error have something timestamp-like:
    errors = capsys.readouterr().err.split('\n')
    assert re.match('^[0-9]{4}', errors[0])
    assert re.match('^WARNING - bar', errors[1])
    assert re.match('^[0-9]{4}', errors[2])

    LOG.removeHandler(log_handler)


def test_log_emit_and_glbl_cfg(
    monkeypatch: pytest.MonkeyPatch, rotating_log_file_handler
):
    """Test that log calls do not access the global config object.

    Doing so can have the side effect of expanding the global config object
    so should be avoided - see https://github.com/cylc/cylc-flow/issues/6244
    """
    rotating_log_file_handler(level=logging.DEBUG)
    mock_cfg = mock.Mock(spec=GlobalConfig)
    monkeypatch.setattr(
        'cylc.flow.cfgspec.globalcfg.GlobalConfig',
        mock.Mock(
            spec=GlobalConfig,
            get_inst=lambda *a, **k: mock_cfg
        )
    )

    # Check mocking is correct:
    glbl_cfg().get(['kinesis'])
    assert mock_cfg.get.call_args_list == [mock.call(['kinesis'])]
    mock_cfg.reset_mock()

    # Check log emit does not access global config object:
    LOG.debug("Entering zero gravity")
    assert mock_cfg.get.call_args_list == []


def test_patch_log_level(caplog: pytest.LogCaptureFixture):
    """Test patch_log_level temporarily changes the log level."""
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger("forest")
    assert logger.level == logging.NOTSET
    logger.setLevel(logging.ERROR)
    logger.info("nope")
    assert not caplog.records
    with patch_log_level(logger, logging.INFO):
        LOG.info("yep")
        assert len(caplog.records) == 1
    logger.info("nope")
    assert len(caplog.records) == 1


def test_patch_log_level__reset(caplog: pytest.LogCaptureFixture):
    """Test patch_log_level resets the log level correctly after use."""
    caplog.set_level(logging.ERROR)
    logger = logging.getLogger("woods")
    assert logger.level == logging.NOTSET
    with patch_log_level(logger, logging.INFO):
        logger.info("emitted but not captured, as caplog is at ERROR level")
        assert not caplog.records
    caplog.set_level(logging.INFO)
    logger.info("yep")
    assert len(caplog.records) == 1
    assert logger.level == logging.NOTSET
