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

from contextlib import suppress
import json
import re
from copy import deepcopy
from time import time
from typing import Any, Dict, List, Optional, Tuple, Callable

from cylc.flow import LOG
import cylc.flow.flags
from cylc.flow.hostuserutil import get_user
from cylc.flow.xtriggers.wall_clock import wall_clock

from cylc.flow.subprocctx import SubFuncContext
from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.data_store_mgr import DataStoreMgr
from cylc.flow.subprocpool import SubProcPool
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.subprocpool import get_func


# Templates for string replacement in function arg values.
TMPL_USER_NAME = 'user_name'
TMPL_WORKFLOW_NAME = 'workflow_name'
TMPL_TASK_CYCLE_POINT = 'point'
TMPL_TASK_IDENT = 'id'
TMPL_TASK_NAME = 'name'
TMPL_WORKFLOW_RUN_DIR = 'workflow_run_dir'
TMPL_WORKFLOW_SHARE_DIR = 'workflow_share_dir'
TMPL_DEBUG_MODE = 'debug'
ARG_VAL_TEMPLATES: List[str] = [
    TMPL_TASK_CYCLE_POINT, TMPL_TASK_IDENT, TMPL_TASK_NAME,
    TMPL_WORKFLOW_RUN_DIR, TMPL_WORKFLOW_SHARE_DIR, TMPL_USER_NAME,
    TMPL_WORKFLOW_NAME, TMPL_DEBUG_MODE
]

# Extract 'foo' from string templates '%(foo)s', avoiding '%%' escaping
# ('%%(foo)s` is not a string template).
RE_STR_TMPL = re.compile(r'(?<!%)%\(([\w]+)\)s')


class XtriggerManager:
    """Manage clock triggers and xtrigger functions.

    # Example:
    [scheduling]
        [[xtriggers]]
            clock_0 = wall_clock()  # offset PT0H
            clock_1 = wall_clock(offset=PT1H)
                 # or wall_clock(PT1H)
            workflow_x = workflow_state(workflow=other,
                                  point=%(task_cycle_point)s):PT30S
        [[graph]]
            PT1H = '''
                @clock_1 & @workflow_x => foo & bar
                @wall_clock = baz  # pre-defined zero-offset clock
            '''

    Task proxies only store xtriggers labels: clock_0, workflow_x, etc. above.
    These are mapped to the defined function calls. Dependence on xtriggers
    is satisfied by calling these functions asynchronously in the task pool
    (except clock triggers which are called synchronously as they're quick).

    A unique call is defined by a unique function call signature, i.e. the
    function name and all arguments. So workflow_x above defines a different
    xtrigger for each cycle point. A new call will not be made before the
    previous one has returned via the xtrigger callback. The interval (in
    "name(args):INTVL") determines frequency of calls (default PT10S).

    Once a trigger is satisfied, remember it until the cleanup cutoff point.

    Clock triggers are treated separately and called synchronously in the main
    process, because they are guaranteed to be quick (but they are still
    managed uniquely - i.e. many tasks depending on the same clock trigger
    (with same offset from cycle point) get satisfied by the same call.

    Args:
        workflow: workflow name
        user: workflow owner
        broadcast_mgr: the Broadcast Manager
        proc_pool: pool of Subprocesses
        workflow_run_dir: workflow run directory
        workflow_share_dir: workflow share directory

    """

    def __init__(
        self,
        workflow: str,
        broadcast_mgr: BroadcastMgr,
        data_store_mgr: DataStoreMgr,
        proc_pool: SubProcPool,
        user: Optional[str] = None,
        workflow_run_dir: Optional[str] = None,
        workflow_share_dir: Optional[str] = None,
    ):
        # Workflow function and clock triggers by label.
        self.functx_map: Dict[str, SubFuncContext] = {}
        # When next to call a function, by signature.
        self.t_next_call: dict = {}
        # Satisfied triggers and their function results, by signature.
        self.sat_xtrig: dict = {}
        # Signatures of active functions (waiting on callback).
        self.active: list = []

        self.workflow_run_dir = workflow_run_dir

        # For function arg templating.
        if not user:
            user = get_user()
        self.farg_templ: Dict[str, Any] = {
            TMPL_WORKFLOW_NAME: workflow,
            TMPL_USER_NAME: user,
            TMPL_WORKFLOW_RUN_DIR: workflow_run_dir,
            TMPL_WORKFLOW_SHARE_DIR: workflow_share_dir,
            TMPL_DEBUG_MODE: cylc.flow.flags.verbosity > 1
        }

        self.proc_pool = proc_pool
        self.broadcast_mgr = broadcast_mgr
        self.data_store_mgr = data_store_mgr

    @staticmethod
    def validate_xtrigger(label: str, fctx: SubFuncContext, fdir: str) -> None:
        """Validate an Xtrigger function.

        Args:
            label: xtrigger label
            fctx: function context
            fdir: function directory
        Raises:
            ImportError: if the function module was not found
            AttributeError: if the function was not found in the xtrigger
                module
            ValueError: if the function is not callable
            ValueError: if any string template in the function context
                arguments are not present in the expected template values.
        """
        fname: str = fctx.func_name
        try:
            func = get_func(fname, fdir)
        except ImportError:
            raise ImportError(
                f"ERROR: xtrigger module '{fname}' not found")
        except AttributeError:
            raise AttributeError(
                f"ERROR: '{fname}' not found in xtrigger module '{fname}'")
        if not callable(func):
            raise ValueError(
                f"ERROR: '{fname}' not callable in xtrigger module '{fname}'")
        # Check any string templates in the function arg values (note this
        # won't catch bad task-specific values - which are added dynamically).
        for argv in fctx.func_args + list(fctx.func_kwargs.values()):
            try:
                for match in RE_STR_TMPL.findall(argv):
                    if match not in ARG_VAL_TEMPLATES:
                        raise ValueError(
                            f"Illegal template in xtrigger {label}: {match}")
            except TypeError:
                # Not a string arg.
                continue

    def add_trig(self, label: str, fctx: SubFuncContext, fdir: str) -> None:
        """Add a new xtrigger function.

        Check the xtrigger function exists here (e.g. during validation).
        Args:
            label: xtrigger label
            fctx: function context
            fdir: function module directory
        """
        self.validate_xtrigger(label, fctx, fdir)
        self.functx_map[label] = fctx

    def mutate_trig(self, label, kwargs):
        self.functx_map[label].func_kwargs.update(kwargs)

    def load_xtrigger_for_restart(self, row_idx: int, row: Tuple[str, str]):
        """Load satisfied xtrigger results from workflow DB.

        Args:
            row_idx (int): row index (used for logging)
            row (Tuple[str, str]): tuple with the signature and results (json)
        Raises:
            ValueError: if the row cannot be parsed as JSON
        """
        if row_idx == 0:
            LOG.info("LOADING satisfied xtriggers")
        sig, results = row
        self.sat_xtrig[sig] = json.loads(results)

    def _get_xtrigs(self, itask: TaskProxy, unsat_only: bool = False,
                    sigs_only: bool = False):
        """(Internal helper method.)

        Args:
            itask (TaskProxy): TaskProxy
            unsat_only (bool): whether to retrieve only unsatisfied xtriggers
                or not
            sigs_only (bool): whether to append only the function signature
                or not
        Returns:
            List[Union[str, Tuple[str, str, SubFuncContext, bool]]]: a list
                with either signature (if sigs_only True) or with tuples of
                label, signature, function context, and flag for satisfied.
        """
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

    def get_xtrig_ctx(self, itask: TaskProxy, label: str) -> SubFuncContext:
        """Get a real function context from the template.

        Args:
            itask: task proxy
            label: xtrigger label
        Returns:
            function context
        """
        farg_templ = {
            TMPL_TASK_CYCLE_POINT: str(itask.point),
            TMPL_TASK_NAME: str(itask.tdef.name),
            TMPL_TASK_IDENT: str(itask.identity)
        }
        farg_templ.update(self.farg_templ)
        ctx = deepcopy(self.functx_map[label])
        kwargs = {}
        args = []
        for val in ctx.func_args:
            with suppress(TypeError):
                val = val % farg_templ
            args.append(val)
        for key, val in ctx.func_kwargs.items():
            with suppress(TypeError):
                val = val % farg_templ
            kwargs[key] = val
        ctx.func_args = args
        ctx.func_kwargs = kwargs
        ctx.update_command(self.workflow_run_dir)
        return ctx

    def call_xtriggers_async(self, itask: TaskProxy):
        """Call itask's xtrigger functions via the process pool...

        ...if previous call not still in-process and retry period is up.


        Args:
            itask: task proxy to check.
        """
        for label, sig, ctx, _ in self._get_xtrigs(itask, unsat_only=True):
            if sig.startswith("wall_clock"):
                # Special case: quick synchronous clock check.
                if 'absolute_as_seconds' not in ctx.func_kwargs:
                    ctx.func_kwargs.update(
                        {
                            'point_as_seconds': itask.get_point_as_seconds()
                        }
                    )
                if wall_clock(*ctx.func_args, **ctx.func_kwargs):
                    itask.state.xtriggers[label] = True
                    self.sat_xtrig[sig] = {}
                    self.data_store_mgr.delta_task_xtrigger(sig, True)
                    LOG.info('xtrigger satisfied: %s = %s', label, sig)
                continue
            # General case: potentially slow asynchronous function call.
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
                            [str(itask.point)],
                            [itask.tdef.name],
                            xtrigger_env
                        )
                continue
            if sig in self.active:
                # Already waiting on this result.
                continue
            now = time()
            if sig in self.t_next_call and now < self.t_next_call[sig]:
                # Too soon to call this one again.
                continue
            self.t_next_call[sig] = now + ctx.intvl
            # Queue to the process pool, and record as active.
            self.active.append(sig)
            self.proc_pool.put_command(ctx, callback=self.callback)

    def housekeep(self, itasks: List[TaskProxy]):
        """Delete satisfied xtriggers no longer needed by any task.

        Args:
            itasks: list of all task proxies.
        """
        all_xtrig = []
        for itask in itasks:
            all_xtrig += self._get_xtrigs(itask, sigs_only=True)
        for sig in list(self.sat_xtrig):
            if sig not in all_xtrig:
                del self.sat_xtrig[sig]

    def callback(self, ctx: SubFuncContext):
        """Callback for asynchronous xtrigger functions.

        Record satisfaction status and function results dict.

        Args:
            ctx (SubFuncContext): function context
        Raises:
            ValueError: if the context given is not active
        """
        LOG.debug(ctx)
        sig = ctx.get_signature()
        self.active.remove(sig)
        try:
            satisfied, results = json.loads(ctx.out)
        except (ValueError, TypeError):
            return
        LOG.debug('%s: returned %s', sig, results)
        if satisfied:
            self.data_store_mgr.delta_task_xtrigger(sig, True)
            LOG.info('xtrigger satisfied: %s = %s', ctx.label, sig)
            self.sat_xtrig[sig] = results

    def check_xtriggers(
            self,
            itask: TaskProxy,
            db_update_func: Callable[[dict], None]) -> bool:
        """Check if all of itasks' xtriggers have become satisfied.

        Return True if satisfied, else False

        Args:
            itasks: task proxs to check
            db_update_func: method to update xtriggers in the DB
        """
        if itask.state.xtriggers_all_satisfied():
            db_update_func(self.sat_xtrig)
            return True
        return False
