#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

from cylc.task_state import task_state
from cylc.TaskID import TaskID
from cylc.gui.DotMaker import DotMaker
from cylc.state_summary import get_id_summary
from cylc.strftime import isoformat_strftime
from copy import deepcopy
import datetime
import gobject
import threading
from time import sleep

def _time_trim(time_value):
    if time_value is not None:
        return time_value.rsplit(".", 1)[0]
    return time_value

class TreeUpdater(threading.Thread):

    def __init__(self, cfg, updater, ttreeview, ttree_paths, info_bar, theme ):

        super(TreeUpdater, self).__init__()

        self.action_required = False
        self.quit = False
        self.cleared = True
        self.autoexpand = True

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
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

        dotm = DotMaker( theme )
        self.dots = {}
        for state in task_state.legal:
            self.dots[ state ] = dotm.get_icon( state )
        self.dots['empty'] = dotm.get_icon()

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
        ctime = model.get_value(model.get_iter(path), 0)
        name = model.get_value(model.get_iter(path), 1)
        if ctime == name:
            # We are hovering over a cycle time row.
            task_id = ctime
        else:
            # We are hovering over a task or family row.
            task_id = name + TaskID.DELIM + ctime
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

        # Retrieve any user-expanded rows so that we can expand them later.
        expand_me = self._get_user_expanded_row_ids()

        new_data = {}
        new_fam_data = {}
        self.ttree_paths.clear()
        for summary, dest in [(self.updater.state_summary, new_data),
                              (self.updater.fam_state_summary, new_fam_data)]:
            # Populate new_data and new_fam_data.
            for id in summary:
                name, ctime = id.split( TaskID.DELIM )
                if ctime not in dest:
                    dest[ ctime ] = {}
                state = summary[ id ].get( 'state' )
                message = summary[ id ].get( 'latest_message', )
                
                tsub = summary[ id ].get( 'submitted_time' )
                if isinstance(tsub, basestring) and tsub != "*":
                    if "T" in tsub:
                        # TODO: get rid of this condition (here for backwards compatibility)
                        tsub = _time_trim( isoformat_strftime(tsub, "%H:%M:%S") ) 
                tstt = summary[ id ].get( 'started_time' )
                tsut = summary[ id ].get( 'succeeded_time' )
                meant = summary[ id ].get( 'mean total elapsed time' )
                tetc = "*"
                if (tstt and (tsut is None or tsut == "*") and
                    self.updater.dt_date is not None and
                    (isinstance(meant, float) or isinstance(meant, int))):
                    try:
                        tstt_date = datetime.datetime.strptime(
                            tstt, "%Y-%m-%dT%H:%M:%S.%f")
                    except (TypeError, ValueError):
                        pass
                    else:
                        run_time = self.updater.dt_date - tstt_date
                        run_time = run_time.days * 86400.0 + run_time.seconds
                        to_go = meant - run_time
                        tetc = isoformat_strftime(
                            (self.updater.dt_date +
                             datetime.timedelta(seconds=to_go)).isoformat(),
                            "%H:%M:%S"
                        )
                if isinstance(tstt, basestring) and tstt != "*":
                    # TODO: get rid of the following condition (here for backwards compatibility)
                    if "T" in tstt:
                        tstt = _time_trim( isoformat_strftime(tstt, "%H:%M:%S") ) 
                if isinstance(meant, float) or isinstance(meant, int):
                    # TODO: get rid of the following condition (here for backwards compatibility)
                    try:
                        meant = int(meant)
                    except (TypeError, ValueError):
                        pass
                    else:
                        meant_hours, remainder = divmod(int(meant), 3600)
                        meant_minutes, meant_seconds = divmod(remainder, 60)
                        meant = "%d:%02d:%02d" % (meant_hours, meant_minutes,
                                                  meant_seconds)
                priority = summary[ id ].get( 'latest_message_priority' )
                try:
                    icon = self.dots[state]
                except KeyError:
                    icon = self.dots['empty']

                dest[ ctime ][ name ] = [ state, message, tsub, tstt, meant, tetc, icon ]

        tree_data = {}
        self.ttreestore.clear()
        times = new_data.keys()
        times.sort()
        for ctime in times:
            f_data = [ None ] * 7
            if "root" in new_fam_data[ctime]:
                f_data = new_fam_data[ctime]["root"]
            piter = self.ttreestore.append(None, [ ctime, ctime ] + f_data )
            family_iters = {}
            name_iters = {}
            task_named_paths = []
            for name in new_data[ ctime ].keys():
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
            task_named_paths.sort()
            for named_path in task_named_paths:
                name = named_path[-1]
                state = new_data[ctime][name][0]
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
                        if fam in new_fam_data[ctime]:
                            f_data = new_fam_data[ctime][fam]
                        f_iter = self.ttreestore.append(
                                      f_iter, [ ctime, fam ] + f_data )
                        family_iters[fam] = f_iter
                    self._update_path_info( f_iter, state, name )
                # Add task to tree
                self.ttreestore.append( f_iter, [ ctime, name ] + new_data[ctime][name])
        if self.autoexpand:
            autoexpand_me = self._get_autoexpand_rows()
            for row_id in list(autoexpand_me):
                if row_id in expand_me:
                    # User expanded row also meets auto-expand criteria.
                    autoexpand_me.remove(row_id)
            expand_me += autoexpand_me
            self._last_autoexpand_me = autoexpand_me
        model = self.ttreeview.get_model()
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
        ctime = model.get_value( riter, 0 )
        name = model.get_value( riter, 1 )
        return (ctime, name)

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
        """Return a list of row ctimes and names that were user expanded."""
        names = []
        model = self.ttreeview.get_model()
        if model is None or model.get_iter_first() is None:
            return names
        self.ttreeview.map_expanded_rows( self._add_expanded_row, names )
        return names

    def _expand_row( self, model, rpath, riter, expand_me ):
        """Expand a row if it matches expand_me ctimes and names."""
        ctime_name_tuple = self._get_row_id( model, rpath )
        if ctime_name_tuple in expand_me:
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

    def _get_autoexpand_rows( self ):
        # Return a list of rows that meet the auto-expansion criteria.
        autoexpand_me = []
        r_iter = self.ttreestore.get_iter_first()
        while r_iter is not None:
            ctime = self.ttreestore.get_value( r_iter, 0 )
            name = self.ttreestore.get_value( r_iter, 1 )
            if (( ctime, name ) not in autoexpand_me and
                self._calc_autoexpand_row( r_iter )):
                # This row should be auto-expanded.
                autoexpand_me.append( ( ctime, name ) )
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
        ctime = self.ttreestore.get_value( row_iter, 0 )
        name = self.ttreestore.get_value( row_iter, 1 )
        if any( [ s in self.autoexpand_states for s in sub_st ] ):
            # return True  # TODO: Option for different expansion rules?
            if ctime == name:
                # Expand cycle times if any child states comply.
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

