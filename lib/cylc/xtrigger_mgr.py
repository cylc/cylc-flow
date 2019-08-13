#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

from copy import deepcopy
import json
import re
from time import time

from cylc import LOG
import cylc.flags
from cylc.hostuserutil import get_user
from cylc.xtriggers.wall_clock import wall_clock
from cylc.subprocpool import get_func


# Templates for string replacement in function arg values.
TMPL_USER_NAME = 'user_name'
TMPL_SUITE_NAME = 'suite_name'
TMPL_TASK_CYCLE_POINT = 'point'
TMPL_TASK_IDENT = 'id'
TMPL_TASK_NAME = 'name'
TMPL_SUITE_RUN_DIR = 'suite_run_dir'
TMPL_SUITE_SHARE_DIR = 'suite_share_dir'
TMPL_DEBUG_MODE = 'debug'
ARG_VAL_TEMPLATES = [
    TMPL_TASK_CYCLE_POINT, TMPL_TASK_IDENT, TMPL_TASK_NAME, TMPL_SUITE_RUN_DIR,
    TMPL_SUITE_SHARE_DIR, TMPL_USER_NAME, TMPL_SUITE_NAME, TMPL_DEBUG_MODE]

# Extract 'foo' from string templates '%(foo)s', avoiding '%%' escaping
# ('%%(foo)s` is not a string template).
RE_STR_TMPL = re.compile(r'(?<!%)%\(([\w]+)\)s')


class XtriggerManager(object):
    """Manage clock triggers and xtrigger functions.

    # Example:
    [scheduling]
        [[xtriggers]]
            clock_0 = wall_clock()  # offset PT0H
            clock_1 = wall_clock(offset=PT1H)
                 # or wall_clock(PT1H)
            suite_x = suite_state(suite=other,
                                  point=%(task_cycle_point)s):PT30S
        [[dependencies]]
            [[[PT1H]]]
                graph = '''
                    @clock_1 & @suite_x => foo & bar
                    @wall_clock = baz  # pre-defined zero-offset clock
                        '''

    Task proxies only store xtriggers labels: clock_0, suite_x, etc. above.
    These are mapped to the defined function calls. Dependence on xtriggers
    is satisfied by calling these functions asynchronously in the task pool
    (except clock triggers which are called synchronously as they're quick).

    A unique call is defined by a unique function call signature, i.e. the
    function name and all arguments. So suite_x above defines a different
    xtrigger for each cycle point. A new call will not be made before the
    previous one has returned via the xtrigger callback. The interval (in
    "name(args):INTVL") determines frequency of calls (default PT10S).

    Once a trigger is satisfied, remember it until the cleanup cutoff point.

    Clock triggers are treated separately and called synchronously in the main
    process, because they are guaranteed to be quick (but they are still
    managed uniquely - i.e. many tasks depending on the same clock trigger
    (with same offset from cycle point) will be satisfied by the same function
    call.

    """

    def __init__(
        self,
        suite,
        user=None,
        broadcast_mgr=None,
        suite_run_dir=None,
        suite_share_dir=None,
        suite_work_dir=None,
        suite_source_dir=None,
    ):
        """Initialize the xtrigger manager."""
        # Suite function and clock triggers by label.
        self.functx_map = {}
        # When next to call a function, by signature.
        self.t_next_call = {}
        # Satisfied triggers and their function results, by signature.
        self.sat_xtrig = {}
        # Signatures of active functions (waiting on callback).
        self.active = []
        # All trigger and clock signatures in the current task pool.
        self.all_xtrig = []

        self.pflag = False

        # For function arg templating.
        if not user:
            user = get_user()
        self.farg_templ = {
            TMPL_SUITE_NAME: suite,
            TMPL_USER_NAME: user,
            TMPL_SUITE_RUN_DIR: suite_run_dir,
            TMPL_SUITE_SHARE_DIR: suite_share_dir,
            TMPL_DEBUG_MODE: cylc.flags.debug
        }
        self.broadcast_mgr = broadcast_mgr
        self.suite_source_dir = suite_source_dir

    def add_trig(self, label, fctx, fdir):
        """Add a new xtrigger function.

        Check the xtrigger function exists here (e.g. during validation).
        """
        try:
            func = get_func(fctx.func_name, fdir)
        except ImportError:
            raise ImportError(
                "ERROR: xtrigger module '%s' not found" % fctx.func_name)
        except AttributeError:
            raise AttributeError(
                "ERROR: attribute '%s' not found in xtrigger module '%s'" % (
                    fctx.func_name, fctx.func_name))
        if not callable(func):
            raise ValueError(
                "ERROR: '%s' in xtrigger module '%s' is not callable" % (
                    fctx.func_name, fctx.func_name))
        self.functx_map[label] = fctx
        # Check any string templates in the function arg values (note this
        # won't catch bad task-specific values - which are added dynamically).
        for argv in fctx.func_args + fctx.func_kwargs.values():
            try:
                for match in RE_STR_TMPL.findall(argv):
                    if match not in ARG_VAL_TEMPLATES:
                        raise ValueError(
                            "Illegal template in xtrigger %s: %s" % (
                                label, match))
            except TypeError:
                # Not a string arg.
                pass

    def load_xtrigger_for_restart(self, row_idx, row):
        """Load satisfied xtrigger results from suite DB."""
        if row_idx == 0:
            LOG.info("LOADING satisfied xtriggers")
        sig, results = row
        self.sat_xtrig[sig] = json.loads(results)

    def housekeep(self):
        """Delete satisfied xtriggers no longer needed."""
        for sig in list(self.sat_xtrig):
            if sig not in self.all_xtrig:
                del self.sat_xtrig[sig]

    def _get_xtrigs(self, itask, unsat_only=False, sigs_only=False):
        """(Internal helper method.)"""
        res = []
        for label, satisfied in itask.state.xtriggers.items():
            if unsat_only and satisfied:
                continue
            ctx = self.get_xtrig_ctx(itask, label)
            sig = ctx.get_signature()
            if sigs_only:
                res.append(sig)
            else:
                res.append((label, sig, ctx, satisfied))
        return res

    def get_xtrig_ctx(self, itask, label):
        """Get a real function context from the template."""
        farg_templ = {
            TMPL_TASK_CYCLE_POINT: str(itask.point),
            TMPL_TASK_NAME: str(itask.tdef.name),
            TMPL_TASK_IDENT: str(itask.identity)
        }
        farg_templ.update(self.farg_templ)
        ctx = deepcopy(self.functx_map[label])
        ctx.point = itask.point
        kwargs = {}
        args = []
        for val in ctx.func_args:
            try:
                val = val % farg_templ
            except TypeError:
                pass
            args.append(val)
        for key, val in ctx.func_kwargs.items():
            try:
                val = val % farg_templ
            except TypeError:
                pass
            kwargs[key] = val
        ctx.func_args = args
        ctx.func_kwargs = kwargs
        ctx.update_command(self.suite_source_dir)
        return ctx

    def collate(self, itasks):
        """Get list of all current xtrigger sigs."""
        self.all_xtrig = []
        for itask in itasks:
            self.all_xtrig += self._get_xtrigs(itask, sigs_only=True)

    def satisfy_xtriggers(self, itask, proc_pool):
        """Attempt to satisfy itask's xtriggers."""
        for label, sig, ctx, _ in self._get_xtrigs(itask, unsat_only=True):
            if sig.startswith("wall_clock"):
                # Special case: synchronous clock check.
                ctx.func_kwargs.update(
                    {
                        'point_as_seconds': itask.get_point_as_seconds(),
                    }
                )
                if wall_clock(*ctx.func_args, **ctx.func_kwargs):
                    itask.state.xtriggers[label] = True
                    self.sat_xtrig[sig] = {}
                    LOG.info('xtrigger satisfied: %s = %s' % (label, sig))
                continue
            # General case: asynchronous xtrigger function call.
            if sig in self.sat_xtrig:
                if not itask.state.xtriggers[label]:
                    itask.state.xtriggers[label] = True
                    res = {}
                    for key, val in self.sat_xtrig[sig].items():
                        res["%s_%s" % (label, key)] = val
                    if res:
                        xtrigger_env = [{'environment': {key: val}} for
                                        key, val in res.items()]
                        self.broadcast_mgr.put_broadcast(
                            [str(ctx.point)],
                            [itask.tdef.name],
                            xtrigger_env
                        )
                continue
            if sig in self.active:
                # Already waiting on this result.
                continue
            now = time()
            if (sig in self.t_next_call and now < self.t_next_call[sig]):
                # Too soon to call this one again.
                continue
            self.t_next_call[sig] = now + ctx.intvl
            # Queue to the process pool, and record as active.
            self.active.append(sig)
            proc_pool.put_command(ctx, self.callback)

    def callback(self, ctx):
        """Callback for asynchronous xtrigger functions.

        Record satisfaction status and function results dict.

        """
        LOG.debug(ctx)
        sig = ctx.get_signature()
        self.active.remove(sig)
        try:
            satisfied, results = json.loads(ctx.out)
        except (ValueError, TypeError):
            return
        LOG.debug('%s: returned %s' % (sig, results))
        if satisfied:
            LOG.info('xtrigger satisfied: %s = %s' % (ctx.label, sig))
            self.pflag = True
            self.sat_xtrig[sig] = results
