#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

from copy import deepcopy
import datetime
import gobject
import threading
from time import sleep

from cylc.task_id import TaskID
from cylc.gui.DotMaker import DotMaker
from cylc.state_summary import get_id_summary
from cylc.strftime import isoformat_strftime
from cylc.wallclock import (
        get_current_time_string,
        get_time_string_from_unix_time,
        TIME_ZONE_STRING_LOCAL_BASIC
)


def _time_trim(time_value):
    if time_value is not None:
        return time_value.rsplit(".", 1)[0]
    return time_value


class TreeUpdater(threading.Thread):

    def __init__(self, cfg, updater, ttreeview, ttree_paths, info_bar, theme, dot_size):

        super(TreeUpdater, self).__init__()

        self.action_required = False
        self.quit = False
        self.cleared = True
        self.autoexpand = True

        self.count = 0

        self.cfg = cfg
        self.updater = updater
        self.info_bar = info_bar
        self.last_update_time = None
        self.ancestors = {}
        self.descendants = []

        self.autoexpand_states = [ 'queued', 'ready', 'submitted', 'running', 'failed' ]
        self._last_autoexpand_me = []
        self.ttree_paths = ttree_paths  # Dict of paths vs all descendant node states
        self.should_group_families = ("text" not in self.cfg.ungrouped_views)
        self.ttreeview = ttreeview
        # Hierarchy of models: view <- sorted <- filtered <- base model
        self.ttreestore = ttreeview.get_model().get_model().get_model()
        self._prev_tooltip_task_id = None
        if hasattr(self.ttreeview, "set_has_tooltip"):
            self.ttreeview.set_has_tooltip(True)
            try:
                self.ttreeview.connect('query-tooltip',
                                       self.on_query_tooltip)
            except TypeError:
                # Lower PyGTK version.
                pass

        # Cache the latest ETC calculation for active ids.
        self._id_tetc_cache = {}

        # Generate task state icons.
        dotm = DotMaker(theme, size=dot_size)
        self.dots = dotm.get_dots()

    def clear_tree( self ):
        self.ttreestore.clear()
        # gtk idle functions must return false or will be called multiple times
        return False

    def update(self):
        if not self.updater.connected:
            if not self.cleared:
                gobject.idle_add(self.clear_tree)
                self.cleared = True
            return False
        self.cleared = False

        if not self.action_required and (
                self.last_update_time is not None and
                self.last_update_time >= self.updater.last_update_time ):
            return False

        self.last_update_time = self.updater.last_update_time

        self.updater.set_update(False)
        self.state_summary = deepcopy(self.updater.state_summary)
        self.fam_state_summary = deepcopy(self.updater.fam_state_summary)
        self.ancestors = deepcopy(self.updater.ancestors)
        self.descendants = deepcopy(self.updater.descendants)
        self.updater.set_update(True)
        return True

    def search_level( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            iter = model.iter_next(iter)
        return None

    def search_treemodel( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            result = self.search_treemodel( model, model.iter_children(iter), func, data)
            if result:
                return result
            iter = model.iter_next(iter)
        return None

    def match_func( self, model, iter, data ):
        column, key = data
        value = model.get_value( iter, column )
        return value == key

    def on_query_tooltip(self, widget, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.ttreeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_task_id = None
            return False
        x, y = self.ttreeview.convert_widget_to_bin_window_coords(x, y)
        path, column, cell_x, cell_y = self.ttreeview.get_path_at_pos(x, y)
        if not path:
            return False
        model = self.ttreeview.get_model()
        point_string = model.get_value(model.get_iter(path), 0)
        name = model.get_value(model.get_iter(path), 1)
        if point_string == name:
            # We are hovering over a cycle point row.
            task_id = point_string
        else:
            # We are hovering over a task or family row.
            task_id = TaskID.get(name, point_string)
        if task_id != self._prev_tooltip_task_id:
            # Clear tooltip when crossing row boundaries.
            self._prev_tooltip_task_id = task_id
            tooltip.set_text(None)
            return False
        text = get_id_summary( task_id, self.state_summary,
                               self.fam_state_summary, self.descendants )
        if text == task_id:
            return False
        tooltip.set_text(text)
        return True

    def update_gui( self ):
        """Update the treeview with new task and family information.

        This redraws the treeview, but keeps a memory of user-expanded
        rows in 'expand_me' so that the tree is still expanded in the
        right places.

        If auto-expand is on, calculate which rows need auto-expansion
        and expand those as well.

        """
        model = self.ttreeview.get_model()

        # Retrieve any user-expanded rows so that we can expand them later.
        expand_me = self._get_user_expanded_row_ids()
        daemon_time_zone_info = self.updater.global_summary.get(
            "daemon time zone info")
        new_data = {}
        new_fam_data = {}
        self.ttree_paths.clear()
        if "T" in self.updater.dt:
            last_update_date = self.updater.dt.split("T")[0]
        else:
            last_update_date = None

        tetc_cached_ids_left = set(self._id_tetc_cache)
        
        for summary, dest in [(self.updater.state_summary, new_data),
                              (self.updater.fam_state_summary, new_fam_data)]:
            # Populate new_data and new_fam_data.
            for id in summary:
                name, point_string = TaskID.split(id)
                if point_string not in dest:
                    dest[ point_string ] = {}
                state = summary[ id ].get('state')

                # Populate task timing slots.
                t_info = {}
                tkeys = ['submitted_time_string', 'started_time_string',
                        'finished_time_string']

                if id in self.fam_state_summary:
                    # Family timing currently left empty.
                    for dt in tkeys:
                        t_info[dt] = ""
                        t_info['mean_total_elapsed_time_string'] = ""
                else:
                    meant = summary[id].get('mean total elapsed time')
                    tstart = summary[id].get('started_time')
                    tetc_string = None

                    for dt in tkeys:
                        try:
                            t_info[dt] = summary[id][dt]
                        except KeyError:
                            # Pre cylc-6 back compat: no special "_string" items,
                            # and the data was in string form already.
                            odt = dt.replace("_string", "")
                            try:
                                t_info[dt] = summary[id][odt]
                            except KeyError:
                                if dt == 'finished_time_string':
                                    # Was succeeded_time.
                                    t_info[dt] = summary[id].get('succeeded_time')
                                else:
                                    t_info[dt] = None
                            if isinstance(t_info[dt], str):
                                # Remove decimal fraction seconds.
                                t_info[dt] = t_info[dt].split('.')[0]

                    if (t_info['finished_time_string'] is None and
                            isinstance(tstart, float) and
                            (isinstance(meant, float) or
                             isinstance(meant, int))):
                        # Task not finished, but has started and has a meant;
                        # so we can compute an expected time of completion.
                        tetc_unix = tstart + meant
                        tetc_string = (
                            self._id_tetc_cache.get(id, {}).get(tetc_unix))
                        if tetc_string is None:
                            # We have to calculate it.
                            tetc_string = get_time_string_from_unix_time(
                                tetc_unix,
                                custom_time_zone_info=daemon_time_zone_info
                            )
                            self._id_tetc_cache[id] = {tetc_unix: tetc_string}
                        t_info['finished_time_string'] = tetc_string
                        estimated_t_finish = True
                    else:
                        estimated_t_finish = False

                    if isinstance(meant, float) or isinstance(meant, int):
                        if meant == 0:
                            # This is a very fast (sub cylc-resolution) task.
                            meant = 1
                        meant = int(meant)
                        meant_minutes, meant_seconds = divmod(meant, 60)
                        if meant_minutes != 0:
                            meant_string = "PT%dM%dS" % (
                                meant_minutes, meant_seconds)
                        else:
                            meant_string = "PT%dS" % meant_seconds
                    elif isinstance(meant,str):
                        meant_string = meant
                    else:
                        meant_string = "*"
                    t_info['mean_total_elapsed_time_string'] = meant_string

                    for dt in tkeys:
                        if t_info[dt] is not None:
                            # Abbreviate time strings in context.
                            t_info[dt] = (
                                self._alter_date_time_string_for_context(
                                    t_info[dt], last_update_date)
                            )
                        else:
                            # Or (no time info yet) use an asterix.
                            t_info[dt] = "*"

                    if estimated_t_finish:
                        # TODO - this markup probably affects sort order?
                        t_info['finished_time_string'] = "<i>%s?</i>" % (
                                t_info['finished_time_string'])
    
                # Use "*" (or "" for family rows) until slot is populated
                # and for pre cylc-6 back compat for host and job ID cols.
                job_id = summary[id].get('submit_method_id')
                batch_sys_name = summary[id].get('batch_sys_name')
                host = summary[id].get('host')
                message = summary[ id ].get('latest_message')
                if message is not None and last_update_date is not None:
                    message = message.replace(last_update_date + "T", "", 1)
                if id in self.fam_state_summary:
                    dot_type = 'family'
                    job_id = job_id or ""
                    batch_sys_name = batch_sys_name or ""
                    host = host or ""
                    message = message or ""
                else:
                    dot_type = 'task'
                    job_id = job_id or "*"
                    batch_sys_name = batch_sys_name or "*"
                    host = host or "*"
                    message = message or "*"

                try:
                    icon = self.dots[dot_type][state]
                except KeyError:
                    icon = self.dots[dot_type]['unknown']

                dest[point_string][name] = [
                        state, host, batch_sys_name, job_id,
                        t_info['submitted_time_string'],
                        t_info['started_time_string'],
                        t_info['finished_time_string'],
                        t_info['mean_total_elapsed_time_string'],
                        message, icon
                ]

        for id in tetc_cached_ids_left:
            # These ids were not present in the summary - so clear them.
            self._id_tetc_cache.pop(id)

        tree_data = {}
        self.ttreestore.clear()
        point_strings = new_data.keys()
        point_strings.sort()

        for point_string in point_strings:
            f_data = [ None ] * 7
            if "root" in new_fam_data[point_string]:
                f_data = new_fam_data[point_string]["root"]
            piter = self.ttreestore.append(
                None, [ point_string, point_string ] + f_data )
            family_iters = {}
            name_iters = {}
            task_named_paths = []
            for name in new_data[ point_string ].keys():
                # The following line should filter by allowed families.
                families = list(self.ancestors[name])
                families.sort(lambda x, y: (y in self.ancestors[x]) -
                                           (x in self.ancestors[y]))
                if "root" in families:
                    families.remove("root")
                if name in families:
                    families.remove(name)
                if not self.should_group_families:
                    families = []
                task_path = families + [name]
                task_named_paths.append(task_path)

            # Sorting here every time the treeview is updated makes
            # definition sort order the default "unsorted" order
            # (any column-click sorting is done on top of this).
            if self.cfg.use_defn_order and self.updater.ns_defn_order:
                task_named_paths.sort( key=lambda x: map( self.updater.dict_ns_defn_order.get, x ) )
            else:
                task_named_paths.sort()

            for named_path in task_named_paths:
                name = named_path[-1]
                state = new_data[point_string][name][0]
                self._update_path_info( piter, state, name )
                f_iter = piter
                for i, fam in enumerate(named_path[:-1]):
                    # Construct family tree for this task.
                    if fam in family_iters:
                        # Family already in tree
                        f_iter = family_iters[fam]
                    else:
                        # Add family to tree
                        f_data = [ None ] * 7
                        if fam in new_fam_data[point_string]:
                            f_data = new_fam_data[point_string][fam]
                        f_iter = self.ttreestore.append(
                                      f_iter, [ point_string, fam ] + f_data )
                        family_iters[fam] = f_iter
                    self._update_path_info( f_iter, state, name )
                # Add task to tree
                self.ttreestore.append(
                    f_iter, [ point_string, name ] + new_data[point_string][name])
        if self.autoexpand:
            autoexpand_me = self._get_autoexpand_rows()
            for row_id in list(autoexpand_me):
                if row_id in expand_me:
                    # User expanded row also meets auto-expand criteria.
                    autoexpand_me.remove(row_id)
            expand_me += autoexpand_me
            self._last_autoexpand_me = autoexpand_me
        if model is None:
            return
        model.get_model().refilter()
        model.sort_column_changed()

        # Expand all the rows that were user-expanded or need auto-expansion.
        model.foreach( self._expand_row, expand_me )

        return False

    def _get_row_id( self, model, rpath ):
        # Record a rows first two values.
        riter = model.get_iter( rpath )
        point_string = model.get_value( riter, 0 )
        name = model.get_value( riter, 1 )
        return (point_string, name)

    def _add_expanded_row( self, view, rpath, expand_me ):
        # Add user-expanded rows to a list of rows to be expanded.
        model = view.get_model()
        row_iter = model.get_iter( rpath )
        row_id = self._get_row_id( model, rpath )
        if (not self.autoexpand or
            row_id not in self._last_autoexpand_me):
            expand_me.append( row_id )
        return False

    def _get_user_expanded_row_ids( self ):
        """Return a list of user-expanded row point_strings and names."""
        names = []
        model = self.ttreeview.get_model()
        if model is None or model.get_iter_first() is None:
            return names
        self.ttreeview.map_expanded_rows( self._add_expanded_row, names )
        return names

    def _expand_row( self, model, rpath, riter, expand_me ):
        """Expand a row if it matches expand_me point_strings and names."""
        point_string_name_tuple = self._get_row_id( model, rpath )
        if point_string_name_tuple in expand_me:
            self.ttreeview.expand_to_path( rpath )
        return False

    def _update_path_info( self, row_iter, descendant_state, descendant_name ):
        # Cache states and names from the subtree below this row.
        path = self.ttreestore.get_path( row_iter )
        self.ttree_paths.setdefault( path, {})
        self.ttree_paths[path].setdefault( 'states', [] )
        self.ttree_paths[path]['states'].append( descendant_state )
        self.ttree_paths[path].setdefault( 'names', [] )
        self.ttree_paths[path]['names'].append( descendant_name )

    def _alter_date_time_string_for_context(self, date_time_string,
                                            context_date_time):
        """Alter a date-time string based on a context date-time."""
        if context_date_time is not None:
            # Remove the date part if it matches the context date.
            date_time_string = date_time_string.replace(
                context_date_time + "T", "", 1)
        return date_time_string

    def _get_autoexpand_rows( self ):
        # Return a list of rows that meet the auto-expansion criteria.
        autoexpand_me = []
        r_iter = self.ttreestore.get_iter_first()
        while r_iter is not None:
            point_string = self.ttreestore.get_value( r_iter, 0 )
            name = self.ttreestore.get_value( r_iter, 1 )
            if (( point_string, name ) not in autoexpand_me and
                self._calc_autoexpand_row( r_iter )):
                # This row should be auto-expanded.
                autoexpand_me.append( ( point_string, name ) )
                # Now check whether the child rows also need this.
                new_iter = self.ttreestore.iter_children( r_iter )
            else:
                # This row shouldn't be auto-expanded, move on.
                new_iter = self.ttreestore.iter_next( r_iter )
                if new_iter is None:
                    new_iter = self.ttreestore.iter_parent( r_iter )
            r_iter = new_iter
        return autoexpand_me

    def _calc_autoexpand_row( self, row_iter ):
        """Calculate whether a row meets the auto-expansion criteria.

        Currently, a family row with tasks in the right states will not
        be expanded, but the tree above it (parents, grandparents, etc)
        will.

        """
        path = self.ttreestore.get_path( row_iter )
        sub_st = self.ttree_paths.get( path, {} ).get( 'states', [] )
        point_string = self.ttreestore.get_value( row_iter, 0 )
        name = self.ttreestore.get_value( row_iter, 1 )
        if any( [ s in self.autoexpand_states for s in sub_st ] ):
            # return True  # TODO: Option for different expansion rules?
            if point_string == name:
                # Expand cycle points if any child states comply.
                return True
            child_iter = self.ttreestore.iter_children( row_iter )
            while child_iter is not None:
                c_path = self.ttreestore.get_path( child_iter )
                c_sub_st = self.ttree_paths.get( c_path,
                                                 {} ).get('states', [] )
                if any( [s in self.autoexpand_states for s in c_sub_st ] ):
                     # Expand if there are sub-families with valid states.
                     # Do not expand if it's just tasks with valid states.
                     return True
                child_iter = self.ttreestore.iter_next( child_iter )
            return False
        return False

    def run(self):
        glbl = None
        states = {}
        while not self.quit:
            if self.update():
                gobject.idle_add( self.update_gui )
            sleep(0.2)
        else:
            pass
            ####print "Disconnecting task state info thread"
