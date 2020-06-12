# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

import pytest

from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.cycling.iso8601 import ISO8601Point, ISO8601Sequence, init
from cylc.flow.subprocctx import SubFuncContext
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.taskdef import TaskDef
from cylc.flow.xtrigger_mgr import XtriggerManager, RE_STR_TMPL


def test_constructor(xtrigger_mgr):
    """Test creating a XtriggerManager, and its initial state."""
    # the dict with normal xtriggers starts empty
    assert not xtrigger_mgr.functx_map


def test_extract_templates():
    """Test escaped templates in xtrigger arg string.

    They should be left alone and passed into the function as string
    literals, not identified as template args.
    """
    assert (
        RE_STR_TMPL.findall('%(cat)s, %(dog)s, %%(fish)s') == ['cat', 'dog']
    )


def test_add_xtrigger(xtrigger_mgr):
    """Test for adding a xtrigger."""
    xtrig = SubFuncContext(
        label="echo",
        func_name="echo",
        func_args=["name", "age"],
        func_kwargs={"location": "soweto"}
    )
    xtrigger_mgr.add_trig("xtrig", xtrig, 'fdir')
    assert xtrig == xtrigger_mgr.functx_map["xtrig"]


def test_add_xtrigger_with_params(xtrigger_mgr):
    """Test for adding a xtrigger."""
    xtrig = SubFuncContext(
        label="echo",
        func_name="echo",
        func_args=["name", "%(point)s"],
        func_kwargs={"%(location)s": "soweto"}  # no problem with the key!
    )
    xtrigger_mgr.add_trig("xtrig", xtrig, 'fdir')
    assert xtrig == xtrigger_mgr.functx_map["xtrig"]


def test_add_xtrigger_with_unknown_params(xtrigger_mgr):
    """Test for adding a xtrigger with an unknown parameter.

    The XTriggerManager contains a list of specific parameters that are
    available in the function template.

    Values that are not strings raise a TypeError during regex matching, but
    are ignored, so we should not have any issue with TypeError.

    If a value in the format %(foo)s appears in the parameters, and 'foo'
    is not in this list of parameters, then a ValueError is expected.
    """
    xtrig = SubFuncContext(
        label="echo",
        func_name="echo",
        func_args=[1, "name", "%(what_is_this)s"],
        func_kwargs={"location": "soweto"}
    )
    with pytest.raises(ValueError):
        xtrigger_mgr.add_trig("xtrig", xtrig, 'fdir')

    # TODO: is it intentional? At the moment when we fail to validate the
    #       function parameters, we add it to the dict anyway.
    assert xtrigger_mgr.functx_map["xtrig"] == xtrig


def test_load_xtrigger_for_restart(xtrigger_mgr):
    """Test loading a xtrigger for restart.

    The function is loaded from database, where the value is formatted
    as JSON."""
    row = "get_name", "{\"name\": \"function\"}"
    xtrigger_mgr.load_xtrigger_for_restart(row_idx=0, row=row)
    assert xtrigger_mgr.sat_xtrig["get_name"]["name"] == "function"


def test_load_invalid_xtrigger_for_restart(xtrigger_mgr):
    """Test loading an invalid xtrigger for restart.

    It simulates that the DB has a value that is not valid JSON.
    """
    row = "get_name", "{name: \"function\"}"  # missing double quotes
    with pytest.raises(ValueError):
        xtrigger_mgr.load_xtrigger_for_restart(row_idx=0, row=row)


def test_housekeeping_nothing_satisfied(xtrigger_mgr):
    """The housekeeping method makes sure only satisfied xtrigger function
    are kept."""
    row = "get_name", "{\"name\": \"function\"}"
    # now XtriggerManager#sat_xtrigger will contain the get_name xtrigger
    xtrigger_mgr.load_xtrigger_for_restart(row_idx=0, row=row)
    assert xtrigger_mgr.sat_xtrig
    xtrigger_mgr.housekeep()
    assert not xtrigger_mgr.sat_xtrig


def test_housekeeping_with_xtrigger_satisfied(xtrigger_mgr):
    """The housekeeping method makes sure only satisfied xtrigger function
    are kept."""
    xtrig = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    xtrigger_mgr.add_trig("get_name", xtrig, 'fdir')
    xtrig.out = "[\"True\", {\"name\": \"Yossarian\"}]"
    tdef = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    init()
    sequence = ISO8601Sequence('P1D', '2019')
    tdef.xtrig_labels[sequence] = ["get_name"]
    start_point = ISO8601Point('2019')
    itask = TaskProxy(tdef=tdef, start_point=start_point)
    xtrigger_mgr.collate([itask])
    # pretend the function has been activated
    xtrigger_mgr.active.append(xtrig.get_signature())
    xtrigger_mgr.callback(xtrig)
    assert xtrigger_mgr.sat_xtrig
    xtrigger_mgr.housekeep()
    # here we still have the same number as before
    assert xtrigger_mgr.sat_xtrig


def test_satisfy_xtrigger(xtrigger_mgr_procpool_broadcast):
    """Test satisfy_xtriggers"""
    # the echo1 xtrig (not satisfied)
    echo1_xtrig = SubFuncContext(
        label="echo1",
        func_name="echo1",
        func_args=[],
        func_kwargs={}
    )

    echo1_xtrig.out = "[\"True\", {\"name\": \"herminia\"}]"
    xtrigger_mgr_procpool_broadcast.add_trig("echo1", echo1_xtrig, "fdir")
    # the echo2 xtrig (satisfied through callback later)
    echo2_xtrig = SubFuncContext(
        label="echo2",
        func_name="echo2",
        func_args=[],
        func_kwargs={}
    )
    echo2_xtrig.out = "[\"True\", {\"name\": \"herminia\"}]"
    xtrigger_mgr_procpool_broadcast.add_trig("echo2", echo2_xtrig, "fdir")
    # create a task
    tdef = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    init()
    sequence = ISO8601Sequence('P1D', '2000')
    tdef.xtrig_labels[sequence] = ["echo1", "echo2"]
    # cycle point for task proxy
    init()
    start_point = ISO8601Point('2019')
    # create task proxy
    itask = TaskProxy(tdef=tdef, start_point=start_point)

    # we start with no satisfied xtriggers, and nothing active
    assert len(xtrigger_mgr_procpool_broadcast.sat_xtrig) == 0
    assert len(xtrigger_mgr_procpool_broadcast.active) == 0

    # after calling satisfy_xtriggers the first time, we get two active
    xtrigger_mgr_procpool_broadcast.satisfy_xtriggers(itask)
    assert len(xtrigger_mgr_procpool_broadcast.sat_xtrig) == 0
    assert len(xtrigger_mgr_procpool_broadcast.active) == 2

    # calling satisfy_xtriggers again does not change anything
    xtrigger_mgr_procpool_broadcast.satisfy_xtriggers(itask)
    assert len(xtrigger_mgr_procpool_broadcast.sat_xtrig) == 0
    assert len(xtrigger_mgr_procpool_broadcast.active) == 2

    # now we call callback manually as the proc_pool we passed is a mock
    # then both should be satisfied
    xtrigger_mgr_procpool_broadcast.callback(echo1_xtrig)
    xtrigger_mgr_procpool_broadcast.callback(echo2_xtrig)
    # so both were satisfied, and nothing is active
    assert len(xtrigger_mgr_procpool_broadcast.sat_xtrig) == 2
    assert len(xtrigger_mgr_procpool_broadcast.active) == 0

    # calling satisfy_xtriggers again still does not change anything
    xtrigger_mgr_procpool_broadcast.satisfy_xtriggers(itask)
    assert len(xtrigger_mgr_procpool_broadcast.sat_xtrig) == 2
    assert len(xtrigger_mgr_procpool_broadcast.active) == 0


def test_collate(xtrigger_mgr):
    """Test that collate properly tallies the totals of current xtriggers."""
    xtrigger_mgr.collate(itasks=[])
    assert not xtrigger_mgr.all_xtrig

    # add a xtrigger
    # that will cause all_xtrig to be populated
    get_name = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    xtrigger_mgr.add_trig("get_name", get_name, 'fdir')
    get_name.out = "[\"True\", {\"name\": \"Yossarian\"}]"
    tdef = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    init()
    sequence = ISO8601Sequence('P1D', '20190101T00Z')
    tdef.xtrig_labels[sequence] = ["get_name"]
    start_point = ISO8601Point('2019')
    itask = TaskProxy(tdef=tdef, start_point=start_point)
    itask.state.xtriggers["get_name"] = get_name

    xtrigger_mgr.collate([itask])
    assert xtrigger_mgr.all_xtrig

    # add a clock xtrigger
    # that will cause both all_xclock to be populated but not all_xtrig
    wall_clock = SubFuncContext(
        label="wall_clock",
        func_name="wall_clock",
        func_args=[],
        func_kwargs={}
    )
    wall_clock.out = "[\"True\", \"1\"]"
    xtrigger_mgr.add_trig("wall_clock", wall_clock, "fdir")
    # create a task
    tdef = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    tdef.xtrig_labels[sequence] = ["wall_clock"]
    start_point = ISO8601Point('20000101T0000+05')
    # create task proxy
    itask = TaskProxy(tdef=tdef, start_point=start_point)

    xtrigger_mgr.collate([itask])
    assert not xtrigger_mgr.all_xtrig


def test_callback_not_active(xtrigger_mgr):
    """Test callback with no active contexts."""
    # calling callback with a SubFuncContext with none active
    # results in a ValueError

    get_name = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    with pytest.raises(ValueError):
        xtrigger_mgr.callback(get_name)


def test_callback_invalid_json(xtrigger_mgr):
    """Test callback with invalid JSON."""
    get_name = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    get_name.out = "{no_quotes: \"mom!\"}"
    xtrigger_mgr.active.append(get_name.get_signature())
    xtrigger_mgr.callback(get_name)
    # this means that the xtrigger was not satisfied
    # TODO: this means site admins are only aware of this if they
    #       look at the debug log. Is that OK?
    assert not xtrigger_mgr.sat_xtrig


def test_callback(xtrigger_mgr):
    """Test callback."""
    get_name = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    get_name.out = "[\"True\", \"1\"]"
    xtrigger_mgr.active.append(get_name.get_signature())
    xtrigger_mgr.callback(get_name)
    # this means that the xtrigger was satisfied
    assert xtrigger_mgr.sat_xtrig


def test_check_xtriggers(xtrigger_mgr_procpool):
    """Test check_xtriggers call.

    check_xtriggers does pretty much the same as collate. The
    difference is that besides tallying on all the xtriggers and
    clock xtriggers available, it then proceeds to trying to
    satisfy them."""

    # add a xtrigger
    # that will cause all_xtrig to be populated, but not all_xclock
    get_name = SubFuncContext(
        label="get_name",
        func_name="get_name",
        func_args=[],
        func_kwargs={}
    )
    xtrigger_mgr_procpool.add_trig("get_name", get_name, 'fdir')
    get_name.out = "[\"True\", {\"name\": \"Yossarian\"}]"
    tdef1 = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    init()
    sequence = ISO8601Sequence('P1D', '2019')
    tdef1.xtrig_labels[sequence] = ["get_name"]
    start_point = ISO8601Point('2019')
    itask1 = TaskProxy(tdef=tdef1, start_point=start_point)
    itask1.state.xtriggers["get_name"] = False  # satisfied?

    # add a clock xtrigger
    # that will cause both all_xclock to be populated but not all_xtrig
    wall_clock = SubFuncContext(
        label="wall_clock",
        func_name="wall_clock",
        func_args=[],
        func_kwargs={}
    )
    wall_clock.out = "[\"True\", \"1\"]"
    xtrigger_mgr_procpool.add_trig("wall_clock", wall_clock, "fdir")
    # create a task
    tdef2 = TaskDef(
        name="foo",
        rtcfg=None,
        run_mode="live",
        start_point=1,
        spawn_ahead=False
    )
    tdef2.xtrig_labels[sequence] = ["wall_clock"]
    init()
    start_point = ISO8601Point('20000101T0000+05')
    # create task proxy
    itask2 = TaskProxy(tdef=tdef2, start_point=start_point)

    xtrigger_mgr_procpool.check_xtriggers([itask1, itask2])
    # won't be satisfied, as it is async, we are are not calling callback
    assert not xtrigger_mgr_procpool.sat_xtrig
    assert xtrigger_mgr_procpool.all_xtrig


# mock objects

class MockedProcPool(SubProcPool):

    def put_command(self, ctx, callback=None, callback_args=None):
        return True


class MockedBroadcastMgr(BroadcastMgr):

    def put_broadcast(
            self, point_strings=None, namespaces=None, settings=None):
        return True

# fixtures


@pytest.fixture
def xtrigger_mgr() -> XtriggerManager:
    """A fixture to build an XtriggerManager that ignores validation.

    Returns:
        XtriggerManager: an XtriggerManager that ignores validation
    """
    xtrigger_mgr = XtriggerManager(
        suite="suitea",
        user="john-foo")
    xtrigger_mgr.validate_xtrigger = lambda fn, fdir: True
    return xtrigger_mgr


@pytest.fixture
def xtrigger_mgr_procpool() -> XtriggerManager:
    """A fixture to build an XtriggerManager that ignores validation,
    and uses a mocked proc_pool.

    Returns:
        XtriggerManager: an XtriggerManager that ignores validation and
            uses a mocked proc_pool
    """
    xtrigger_mgr = XtriggerManager(
        suite="suitea",
        user="john-foo",
        proc_pool=MockedProcPool()
    )
    xtrigger_mgr.validate_xtrigger = lambda fn, fdir: True
    return xtrigger_mgr


@pytest.fixture
def xtrigger_mgr_procpool_broadcast() -> XtriggerManager:
    """A fixture to build an XtriggerManager that ignores validation,
    uses a mocked proc_pool, and uses a mocked broadacast_mgr.

    Returns:
        XtriggerManager: an XtriggerManager that ignores validation,
            uses a mocked proc_pool, and uses a mocked broadacast_mgr
    """
    xtrigger_mgr = XtriggerManager(
        suite="sample_suite",
        user="john-foo",
        proc_pool=MockedProcPool(),
        broadcast_mgr=MockedBroadcastMgr(suite_db_mgr=None)
    )
    xtrigger_mgr.validate_xtrigger = lambda fn, fdir: True
    return xtrigger_mgr
