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
from unittest.mock import Mock

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import (
    CylcConfigError, CylcError, HostSelectException
)
from cylc.flow.main_loop.auto_restart import (
    _can_auto_restart,
    _set_auto_restart,
    _should_auto_restart,
    auto_restart,
)
from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.scheduler import Scheduler
from cylc.flow.workflow_status import (
    AutoRestartMode,
    StopMode
)


def test_can_auto_restart_pass(monkeypatch, caplog):
    """Test can_auto_restart for successful host selection."""
    def select_workflow_host(**_):
        return ('localhost', 'localhost')
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_workflow_host',
        select_workflow_host
    )
    assert _can_auto_restart()
    assert caplog.record_tuples == []


def test_can_auto_restart_fail(monkeypatch, caplog):
    """Test can_auto_restart for unsuccessful host selection."""
    def select_workflow_host(**_):
        raise HostSelectException({})
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_workflow_host',
        select_workflow_host
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert not _can_auto_restart()
        [(_, level, msg)] = caplog.record_tuples
        assert level == logging.CRITICAL
        assert 'No alternative host to restart workflow on' in msg


def test_can_auto_restart_fail_horribly(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Test can_auto_restart for really unsuccessful host selection."""
    def select_workflow_host(**_):
        raise Exception('Unexpected error in host selection')
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_workflow_host',
        select_workflow_host
    )
    with caplog.at_level(level=logging.ERROR, logger=CYLC_LOG):
        assert not _can_auto_restart()
        assert 'Error in host selection' in caplog.text
        assert "Traceback (most recent call last):" in caplog.text


@pytest.mark.parametrize(
    'host, stop_mode, condemned_hosts,'
    ' auto_restart_time, should_auto_restart',
    [
        (  # no reason to restart, no reason not to
            'localhost',
            None,
            [],
            None,
            False
        ),
        (  # should restart but already stopping
            'localhost',
            StopMode.AUTO,
            ['localhost'],
            None,
            False
        ),
        (  # stop restart but already auto-restarting
            'localhost',
            StopMode.AUTO,
            ['localhost'],
            12345,
            False
        ),
        (  # should restart
            'localhost',
            None,
            ['localhost'],
            None,
            AutoRestartMode.RESTART_NORMAL
        ),
        (  # should force stop
            'localhost',
            None,
            ['localhost!'],
            None,
            AutoRestartMode.FORCE_STOP
        )
    ]
)
def test_should_auto_restart(
        host,
        stop_mode,
        condemned_hosts,
        auto_restart_time,
        should_auto_restart,
        monkeypatch
):
    """Ensure the workflow only auto-restarts when appropriate."""
    # factor out networking and FQDNs for testing purposes
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.get_fqdn_by_host',
        lambda x: x
    )
    # mock a scheduler object
    scheduler = Mock(
        host=host,
        stop_mode=stop_mode,
        auto_restart_time=auto_restart_time
    )
    # mock a workflow configuration object
    cfg = Mock()
    cfg.get = lambda x: condemned_hosts
    # test
    assert _should_auto_restart(scheduler, cfg) == should_auto_restart


def test_set_auto_restart_already_stopping(caplog):
    """Ensure restart isn't attempted if already stopping."""
    scheduler = Mock(
        stop_mode=StopMode.AUTO
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert _set_auto_restart(scheduler)
        assert caplog.record_tuples == []


def test_set_auto_restart_force_oveeride(caplog):
    """Ensure scheduled restart is cancelled for a force stop."""
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=1234
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert _set_auto_restart(
            scheduler,
            mode=AutoRestartMode.FORCE_STOP,
        )
        assert len(caplog.record_tuples) == 2
        [
            (*_, msg1),
            (*_, msg2)
        ] = caplog.record_tuples
        assert 'This workflow will be shutdown' in msg1
        assert 'Scheduled automatic restart canceled' in msg2


def test_set_auto_restart_already_restarting(caplog):
    """Ensure restart isn't re-scheduled."""
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=1234
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert _set_auto_restart(scheduler)
        assert caplog.record_tuples == []


def test_set_auto_restart_no_detach(caplog: pytest.LogCaptureFixture):
    """Ensure raises a CylcError (or subclass) if running in no-detach mode."""
    scheduler = Mock(
        spec=Scheduler,
        stop_mode=None,
        auto_restart_time=None,
        options=Mock(no_detach=True)
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        with pytest.raises(CylcError):
            _set_auto_restart(scheduler)
        assert caplog.record_tuples == []


def test_set_auto_restart_unable_to_restart(monkeypatch):
    """Ensure returns False if workflow is unable to restart"""
    called = False

    def workflow_select_fail(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return False

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        workflow_select_fail
    )
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=None,
        options=Mock(no_detach=False)
    )
    assert not _set_auto_restart(
        scheduler
    )
    assert called


def test_set_auto_restart_with_delay(monkeypatch, caplog):
    """Ensure workflows wait for a period before auto-restarting."""
    called = False

    def workflow_select_pass(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return True

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        workflow_select_pass
    )
    monkeypatch.setattr(
        # remove the random element of the restart delay
        'cylc.flow.main_loop.auto_restart.random',
        lambda: 1
    )
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=None,
        options=Mock(no_detach=False)
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert _set_auto_restart(
            scheduler,
            restart_delay=1
        )
        [(*_, msg1), (*_, msg2)] = caplog.record_tuples
        assert 'will automatically restart' in msg1
        assert 'will restart in 1s' in msg2
    assert called


def test_set_auto_restart_without_delay(monkeypatch, caplog):
    """Ensure workflows auto-restart when no delay is provided."""
    called = False

    def workflow_select_pass(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return True

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        workflow_select_pass
    )
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=None,
        options=Mock(no_detach=False)
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert _set_auto_restart(
            scheduler
        )
        [(*_, msg)] = caplog.record_tuples
        assert 'will automatically restart' in msg
    assert called


@pytest.mark.parametrize('exc_class', [ParsecError, CylcConfigError])
async def test_log_config_error(caplog, log_filter, monkeypatch, exc_class):
    """It should log errors in the global config.

    When errors are present in the global config they should be caught and
    logged nicely rather than left to spill over as traceback in the log.
    """
    # make the global config raise an error
    def global_config_load_error(*args, **kwargs):
        raise exc_class('something even more bizarrely inexplicable')

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.glbl_cfg',
        global_config_load_error,
    )

    # call the auto_restart plugin, the error should be caught
    caplog.clear()
    assert await auto_restart(None, None) is False

    # the error should have been logged
    assert len(caplog.messages) == 1
    assert 'an error in the global config' in caplog.messages[0]
    assert 'something even more bizarrely inexplicable' in caplog.messages[0]
