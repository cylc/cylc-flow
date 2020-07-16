import logging
from unittest.mock import Mock

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import HostSelectException
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.main_loop.auto_restart import (
    _should_auto_restart,
    _can_auto_restart,
    _set_auto_restart
)
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.suite_status import (
    AutoRestartMode,
    StopMode
)


def test_can_auto_restart_pass(monkeypatch, caplog):
    """Test can_auto_restart for successful host selection."""
    def select_suite_host(**_):
        return ('localhost', 'localhost')
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_suite_host',
        select_suite_host
    )
    assert _can_auto_restart()
    assert caplog.record_tuples == []


def test_can_auto_restart_fail(monkeypatch, caplog):
    """Test can_auto_restart for unsuccessful host selection."""
    def select_suite_host(**_):
        raise HostSelectException({})
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_suite_host',
        select_suite_host
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert not _can_auto_restart()
        [(_, level, msg)] = caplog.record_tuples
        assert level == logging.CRITICAL
        assert 'No alternative host to restart suite on' in msg


def test_can_auto_restart_fail_horribly(monkeypatch, caplog):
    """Test can_auto_restart for really unsuccessful host selection."""
    def select_suite_host(**_):
        raise Exception('Unexpected error in host selection')
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart.select_suite_host',
        select_suite_host
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        assert not _can_auto_restart()
        [(_, level, msg)] = caplog.record_tuples
        assert level == logging.CRITICAL
        assert 'Error in host selection' in msg


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
        should_auto_restart
):
    """Ensure the suite only auto-restarts when appropriate."""
    # mock a scheduler object
    scheduler = Mock(
        host=get_fqdn_by_host(host),
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
        assert 'This suite will be shutdown' in msg1
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


def test_set_auto_restart_no_detach(caplog):
    """Ensure raises RuntimeError if running in no-detach mode."""
    scheduler = Mock(
        stop_mode=None,
        auto_restart_time=None,
        options=Mock(no_detach=True)
    )
    with caplog.at_level(level=logging.DEBUG, logger=CYLC_LOG):
        with pytest.raises(RuntimeError):
            _set_auto_restart(scheduler)
        assert caplog.record_tuples == []


def test_set_auto_restart_unable_to_restart(monkeypatch):
    """Ensure returns False if suite is unable to restart"""
    called = False

    def suite_select_fail(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return False

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        suite_select_fail
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
    """Ensure suites wait for a period before auto-restarting."""
    called = False

    def suite_select_pass(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return True

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        suite_select_pass
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
    """Ensure suites auto-restart when no delay is provided."""
    called = False

    def suite_select_pass(**_):
        nonlocal called
        called = True  # prevent this becoming a placebo
        return True

    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._can_auto_restart',
        suite_select_pass
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
