from typing import TYPE_CHECKING

from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point
from cylc.flow.main_loop import (
    periodic,
    startup,
    submit,
)
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_WAITING,
)
from cylc.flow.wallclock import now

from metomi.isodatetime.data import get_timepoint_for_now
from metomi.isodatetime.parsers import DurationParser

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


@startup
async def setup(schd: 'Scheduler', state: dict):
    # the greatest clock-expire offset from the cycle point
    # (this is the furthest ahead of the current time that we need to
    # look for expired tasks)
    state['max_offset'] = max(
        offset
        for offset in schd.config.expiration_offsets.values()
    )
    # all clock-expire'able tasks within the window 
    state['timeouts'] = {}
    # the point we have populated the timouts list up to
    state['expire_point'] = schd.config.initial_point


@periodic
async def check_clock_expires(schd: 'Scheduler', state: dict):
    """Check for clock-expired tasks."""
    time = get_timepoint_for_now()
    add_timeouts(schd, state, time)
    check_timeouts(schd, state, time)


@submit
async def remove_timeout(schd, state, itasks):
    """Remove a task from expire timeouts, called when tasks are submitted."""
    for itask in itasks:
        key = (itask.tokens['cycle'], itask.tokens['task'])
        if key in state['timeouts']:
            state['timeouts'].pop(key)


def check_timeouts(schd: 'Scheduler', state, time):
    """Check for expired tasks in the timeouts dict."""
    time = get_point(str(time))
    timeouts = state['timeouts']

    pop = []
    for (point, task), timeout in timeouts.items():
        if time > timeout:
            if clock_expire_task(schd, point, task):
                pop.append((point, task))

    for point, task in pop:
        timeouts.pop((point, task))


def add_timeouts(schd: 'Scheduler', state: dict, time):
    """Expand the expire window and add new tasks to the timeouts dict."""
    # the furthest we have looked ahead so far
    old_expire_point = state['expire_point']
    # the furthest we should look ahead now
    new_expire_point = time + DurationParser().parse(state['max_offset'].value)

    # expand the window out to "new_expire_point"
    timeouts = state['timeouts']
    for recurrence, tasks in schd.config.sequences.items():
        point = recurrence.get_next_point(old_expire_point)
        if point is None:
            # end of sequence => skip
            continue
        while point <= get_point(str(new_expire_point)):
            # TODO: avoid looping all tasks in each sequence
            for task in tasks:
                if task in schd.config.expiration_offsets:
                    # add expiration timeout
                    timeouts[(point, task)] = (
                        schd.config.expiration_offsets[task]
                        + point
                    )
            point = recurrence.get_next_point(point)
    
    state['expire_point'] = get_point(str(new_expire_point))


def clock_expire_task(schd, point, task):
    """Expire a task."""
    print(f'clock_expire_task({point}, {task})')
    itask = schd.pool.get_task(point, task)
    if (
        itask
        and not itask.state(
            TASK_STATUS_WAITING,
            is_held=False
        )
    ):
        # don't expire this task, it is held
        return False

    if not itask:
        itask = schd.pool.spawn_task(
            task,
            point,
            {1},  # TODO use flow=all?
            # TODO: wait=true?
        )

    msg = 'Task expired (skipping job).'
    LOG.warning(f"[{point}/{task}] {msg}")
    schd.task_events_mgr.setup_event_handlers(itask, "expired", msg)
    # TODO succeeded and expired states are useless due to immediate
    # removal under all circumstances (unhandled failed is still used).
    if itask.state_reset(TASK_STATUS_EXPIRED, is_held=False):
        schd.data_store_mgr.delta_task_state(itask)
        schd.data_store_mgr.delta_task_held(itask)
    return True
