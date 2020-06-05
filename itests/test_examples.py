import asyncio
import logging
from pathlib import Path

import pytest


# the suite log is returned by run_flow()

@pytest.mark.asyncio
async def test_cylc_version(flow, scheduler, run, one_conf):
    """Ensure the flow logs the cylc version 8.0a1."""
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd) as log:
        assert (
            ('cylc', logging.INFO, 'Cylc version: 8.0a1')
            in log.record_tuples
        )


# command line options can be provided to flow() using their "dest" names

@pytest.mark.asyncio
async def test_hold_start(flow, scheduler, run, one_conf):
    """Ensure the flow starts in held mode when run with hold_start=True."""
    reg = flow(one_conf)
    schd = scheduler(reg, hold_start=True)
    async with run(schd):
        assert schd.paused()
    reg = flow(one_conf)
    schd = scheduler(reg, hold_start=False)
    async with run(schd):
        assert not schd.paused()


# when the flow stops the scheduler object is still there for us to poke

@pytest.mark.asyncio
async def test_shutdown(flow, scheduler, run, one_conf):
    """Ensure the server shutsdown with the flow."""
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        await schd.shutdown('because i said so')
        assert schd.server.socket.closed


# you don't have to run suites, infact we should avoid it when possible

@pytest.mark.asyncio
async def test_install(flow, scheduler, one_conf, run_dir):
    """Ensure the installation of the job script is completed."""
    reg = flow(one_conf)
    schd = scheduler(reg)
    await schd.install()
    assert Path(
        run_dir, schd.suite, '.service', 'etc', 'job.sh'
    ).exists()


@pytest.mark.asyncio
async def test_run(flow, scheduler, run, one_conf):
    """Ensure the scheduler can stay alive for 2 seconds."""
    reg = flow(one_conf)
    schd = scheduler(reg)
    async with run(schd):
        await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_exception(flow, scheduler, run, one_conf, log_filter):
    """"""
    reg = flow(one_conf)
    schd = scheduler(reg)

    # replace the main loop with something that raises an exception
    def killer():
        raise Exception('mess')

    schd.main_loop = killer

    # make sure that this error causes the flow to shutdown
    async with run(schd) as log:
        # evil sleep - gotta let the except mechanism do its work
        await asyncio.sleep(0.1)
        # make sure the exception was logged
        assert len(log_filter(
            log,
            level=logging.CRITICAL,
            contains='mess'
        )) == 1
        # make sure the server socket has closed - a good indication of a
        # successful clean shutdown
        assert schd.server.socket.closed
