import logging
from pathlib import Path

import pytest


# the suite log is returned by run_flow()

@pytest.mark.asyncio
async def test_cylc_version(flow, run_flow, simple_conf):
    """Ensure the flow logs the cylc version 8.0a1."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler) as log:
        assert (
            ('cylc', logging.INFO, 'Cylc version: 8.0a1')
            in log.record_tuples
        )


# command line options can be provided to flow() using their "dest" names

@pytest.mark.asyncio
async def test_hold_start(flow, run_flow, simple_conf):
    """Ensure the flow starts in held mode when run with hold_start=True."""
    scheduler = flow(simple_conf, hold_start=True)
    async with run_flow(scheduler):
        assert scheduler.paused()


# when the flow stops the scheduler object is still there for us to poke

@pytest.mark.asyncio
async def test_shutdown(flow, run_flow, simple_conf):
    """Ensure the server shutsdown with the flow."""
    scheduler = flow(simple_conf)
    async with run_flow(scheduler):
        await scheduler.shutdown('because i said so')
        assert scheduler.server.socket.closed


# you don't have to run suites, infact we should avoid it when possible

@pytest.mark.asyncio
async def test_install(flow, run_flow, simple_conf, run_dir):
    """Ensure the flow starts in held mode when run with hold_start=True."""
    scheduler = flow(simple_conf)
    jobscript = Path(run_dir, scheduler.suite, '.service', 'etc', 'job.sh')
    assert jobscript.exists()
