#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
import gobject
import os
import re
import threading
from time import sleep
import traceback

from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.graphing import CGraphPlain
from cylc.gui.warning_dialog import warning_dialog
from cylc.gui.util import get_id_summary
from cylc.mkdir_p import mkdir_p
from cylc.network.httpclient import ClientError
from cylc.task_id import TaskID
from cylc.task_state import TASK_STATUS_RUNAHEAD


def compare_dict_of_dict(one, two):
    """Return True if one == two, else return False."""
    for key in one:
        if key not in two:
            return False
        for subkey in one[key]:
            if subkey not in two[key]:
                return False
            if one[key][subkey] != two[key][subkey]:
                return False

    for key in two:
        if key not in one:
            return False
        for subkey in two[key]:
            if subkey not in one[key]:
                return False
            if two[key][subkey] != one[key][subkey]:
                return False

    return True


class GraphUpdater(threading.Thread):
    def __init__(self, cfg, updater, theme, info_bar, xdot):
        super(GraphUpdater, self).__init__()

        self.quit = False
        self.cleared = False
        self.ignore_suicide = True
        self.focus_start_point_string = None
        self.focus_stop_point_string = None
        self.xdot = xdot
        self.first_update = False
        self.graph_disconnect = False
        self.action_required = True
        self.oldest_point_string = None
        self.newest_point_string = None
        self.orientation = "TB"  # Top to Bottom ordering of nodes
        self.best_fit = True  # zoom to page size
        self.normal_fit = False  # zoom to 1.0 scale
        self.crop = False
        self.subgraphs_on = False   # organise by cycle point.

        self.descendants = {}
        self.all_families = []
        self.write_dot_frames = False

        self.prev_graph_id = ()

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.info_bar = info_bar
        self.state_summary = {}
        self.fam_state_summary = {}
        self.global_summary = {}
        self.last_update_time = None

        self.god = None
        self.mode = "waiting..."
        self.update_time_str = "waiting..."

        self.prev_graph_id = ()

        # empty graphw object:
        self.graphw = CGraphPlain(self.cfg.suite)

        # lists of nodes to newly group or ungroup (not of all currently
        # grouped and ungrouped nodes - still held server side)
        self.group = []
        self.ungroup = []
        self.have_leaves_and_feet = False
        self.leaves = []
        self.feet = []

        self.ungroup_recursive = False
        if "graph" in self.cfg.ungrouped_views:
            self.ungroup_all = True
            self.group_all = False
        else:
            self.ungroup_all = False
            self.group_all = True

        self.graph_frame_count = 0
        self.suite_share_dir = glbl_cfg().get_derived_host_item(
            self.cfg.suite, 'suite share directory')

    def toggle_write_dot_frames(self):
        self.write_dot_frames = not self.write_dot_frames
        if self.write_dot_frames:
            # Create local share dir if necessary (could be a remote suite).
            try:
                mkdir_p(self.suite_share_dir)
            except Exception as exc:
                gobject.idle_add(warning_dialog(
                    "%s\nCannot create graph frames directory." % (str(exc))
                ).warn)
                self.write_dot_frames = False

    def clear_gui(self):
        """Clear the graph GUI."""
        self.prev_graph_id = ()
        self.graphw = CGraphPlain(self.cfg.suite)
        self.normal_fit = True
        self.update_xdot()
        # gtk idle functions must return false or will be called multiple times
        return False

    def get_summary(self, task_id):
        """Return some state information about a task or family."""
        return get_id_summary(
            task_id, self.state_summary, self.fam_state_summary,
            self.descendants)

    def update(self):
        """Update data using data from self.updater."""
        if not self.updater.connected:
            if not self.cleared:
                gobject.idle_add(self.clear_gui)
                self.cleared = True
            return False
        self.cleared = False

        if (self.last_update_time is not None and
                self.last_update_time >= self.updater.last_update_time):
            if self.action_required:
                return True
            return False

        self.updater.no_update_event.set()
        states_full = deepcopy(self.updater.state_summary)
        fam_states_full = deepcopy(self.updater.fam_state_summary)
        self.ancestors = deepcopy(self.updater.ancestors)
        self.descendants = deepcopy(self.updater.descendants)
        self.all_families = deepcopy(self.updater.all_families)
        self.global_summary = deepcopy(self.updater.global_summary)
        self.updater.no_update_event.clear()

        self.first_update = (self.last_update_time is None)
        self.last_update_time = self.updater.last_update_time

        # The graph layout is not stable even when (py)graphviz is
        # presented with the same graph (may be a node ordering issue
        # due to use of dicts?). For this reason we only plot node name
        # and color (state) and only replot when node content or states
        # change.  The full state summary contains task timing
        # information that changes continually, so we have to disregard
        # this when checking for changes. So: just extract the critical
        # info here:
        states = {}
        for id_, state_full in states_full.items():
            if id_ not in states:
                states[id_] = {}
            for key in [
                    'name', 'description', 'title', 'label', 'state',
                    'submit_num']:
                if key in state_full:  # ensure backward compatible
                    states[id_][key] = state_full[key]

        f_states = {}
        for id_, fam_state_full in fam_states_full.items():
            if id_ not in states:
                f_states[id_] = {}
            for key in ['name', 'description', 'title', 'label', 'state']:
                if key in fam_state_full:  # ensure backward compatible
                    f_states[id_][key] = fam_state_full[key]

        if states and not self.state_summary:
            # This is basically equivalent to a first-update case.
            self.first_update = True

        # only update states if a change occurred, or action required
        if self.action_required:
            self.state_summary = states
            self.fam_state_summary = f_states
            return True
        elif self.graph_disconnect:
            return False
        elif not compare_dict_of_dict(states, self.state_summary):
            # state changed - implicitly includes family state change.
            self.state_summary = states
            self.fam_state_summary = f_states
            return True
        else:
            return False

    def run(self):
        while not self.quit:
            if self.update():
                self.update_gui()
            sleep(0.2)

    def update_xdot(self, no_zoom=False):
        self.xdot.set_dotcode(self.graphw.to_string(), no_zoom=no_zoom)
        if self.first_update:
            self.xdot.widget.zoom_to_fit()
            self.first_update = False
        elif self.best_fit:
            self.xdot.widget.zoom_to_fit()
            self.best_fit = False
        elif self.normal_fit:
            self.xdot.widget.zoom_image(1.0, center=True)
            self.normal_fit = False

    def set_live_node_attr(self, node, id_, shape=None):
        # override base graph URL to distinguish live tasks
        node.attr['URL'] = id_
        if id_ in self.state_summary:
            state = self.state_summary[id_]['state']
        else:
            state = self.fam_state_summary[id_]['state']

        try:
            node.attr['style'] = 'bold,' + self.theme[state]['style']
            node.attr['fillcolor'] = self.theme[state]['color']
            node.attr['color'] = self.theme[state]['color']
            node.attr['fontcolor'] = self.theme[state]['fontcolor']
        except KeyError:
            # unknown state
            node.attr['style'] = 'unfilled'
            node.attr['color'] = 'black'
            node.attr['fontcolor'] = 'black'

        if shape:
            node.attr['shape'] = shape

    def update_gui(self):
        # TODO - check edges against resolved ones
        # (adding new ones, and nodes, if necessary)
        self.action_required = False
        if not self.global_summary:
            return

        self.oldest_point_string = (
            self.global_summary['oldest cycle point string'])
        self.newest_point_string = (
            self.global_summary['newest cycle point string'])
        if TASK_STATUS_RUNAHEAD not in self.updater.filter_states_excl:
            # Get a graph out to the max runahead point.
            self.newest_point_string = (
                self.global_summary[
                    'newest runahead cycle point string'])

        if self.focus_start_point_string:
            oldest = self.focus_start_point_string
            newest = self.focus_stop_point_string
        else:
            oldest = self.oldest_point_string
            newest = self.newest_point_string

        group_for_server = self.group
        if self.group == []:
            group_for_server = None

        ungroup_for_server = self.ungroup
        if self.ungroup == []:
            ungroup_for_server = None

        try:
            res = self.updater.client.get_info(
                'get_graph_raw', start_point_string=oldest,
                stop_point_string=newest,
                group_nodes=group_for_server,
                ungroup_nodes=ungroup_for_server,
                ungroup_recursive=self.ungroup_recursive,
                group_all=self.group_all,
                ungroup_all=self.ungroup_all
            )
        except ClientError:
            if cylc.flags.debug:
                try:
                    traceback.print_exc()
                except IOError:
                    pass  # Cannot print to terminal (session may be closed).

            return False

        self.have_leaves_and_feet = True
        gr_edges, suite_polling_tasks, self.leaves, self.feet = res
        gr_edges = [tuple(edge) for edge in gr_edges]

        current_id = self.get_graph_id(gr_edges)
        if current_id != self.prev_graph_id:
            self.graphw = CGraphPlain(
                self.cfg.suite, suite_polling_tasks)
            self.graphw.add_edges(
                gr_edges, ignore_suicide=self.ignore_suicide)

            nodes_to_remove = set()

            # Remove nodes representing filtered-out tasks.
            if (self.updater.filter_name_string or
                    self.updater.filter_states_excl):
                for node in self.graphw.nodes():
                    id_ = node.get_name()
                    # Don't need to guard against special nodes here (yet).
                    name, point_string = TaskID.split(id_)
                    if name not in self.all_families:
                        # This node is a task, not a family.
                        if id_ in self.updater.filt_task_ids:
                            nodes_to_remove.add(node)
                        elif id_ not in self.updater.kept_task_ids:
                            # A base node - these only appear in the graph.
                            filter_string = self.updater.filter_name_string
                            if (filter_string and
                                    filter_string not in name and
                                    not re.search(filter_string, name)):
                                # A base node that fails the name filter.
                                nodes_to_remove.add(node)
                    elif id_ in self.fam_state_summary:
                        # Remove family nodes if all members filtered out.
                        remove = True
                        for mem in self.descendants[name]:
                            mem_id = TaskID.get(mem, point_string)
                            if mem_id in self.updater.kept_task_ids:
                                remove = False
                                break
                        if remove:
                            nodes_to_remove.add(node)
                    elif id_ in self.updater.full_fam_state_summary:
                        # An updater-filtered-out family.
                        nodes_to_remove.add(node)

            # Base node cropping.
            if self.crop:
                # Remove all base nodes.
                for node in (set(self.graphw.nodes()) - nodes_to_remove):
                    if node.get_name() not in self.state_summary:
                        nodes_to_remove.add(node)
            else:
                # Remove cycle points containing only base nodes.
                non_base_point_strings = set()
                point_string_nodes = {}
                for node in set(self.graphw.nodes()) - nodes_to_remove:
                    node_id = node.get_name()
                    name, point_string = TaskID.split(node_id)
                    point_string_nodes.setdefault(point_string, [])
                    point_string_nodes[point_string].append(node)
                    if (node_id in self.state_summary or
                            node_id in self.fam_state_summary):
                        non_base_point_strings.add(point_string)
                pure_base_point_strings = (
                    set(point_string_nodes) - non_base_point_strings)
                for point_string in pure_base_point_strings:
                    for node in point_string_nodes[point_string]:
                        nodes_to_remove.add(node)
            self.graphw.cylc_remove_nodes_from(list(nodes_to_remove))
            # TODO - remove base nodes only connected to other base nodes?
            # Should these even exist any more?

            # Make family nodes octagons.
            for node in self.graphw.nodes():
                node_id = node.get_name()
                try:
                    name, point_string = TaskID.split(node_id)
                except ValueError:
                    # Special node.
                    continue
                if name in self.all_families:
                    node.attr['shape'] = 'doubleoctagon'

            if self.subgraphs_on:
                self.graphw.add_cycle_point_subgraphs(gr_edges)

        # Set base node style defaults
        for node in self.graphw.nodes():
            node.attr.setdefault('style', 'filled')
            node.attr['color'] = '#888888'
            node.attr['fillcolor'] = 'white'
            node.attr['fontcolor'] = '#888888'
            node.attr['URL'] = 'base:%s' % node.attr['URL']

        for id_ in self.state_summary:
            try:
                node = self.graphw.get_node(id_)
            except KeyError:
                continue
            self.set_live_node_attr(node, id_)

        for id_ in self.fam_state_summary:
            try:
                node = self.graphw.get_node(id_)
            except KeyError:
                # Node not in graph.
                continue
            self.set_live_node_attr(node, id_)

        self.graphw.graph_attr['rankdir'] = self.orientation

        if self.write_dot_frames:
            arg = os.path.join(
                self.suite_share_dir, 'frame' + '-' +
                str(self.graph_frame_count) + '.dot')
            self.graphw.write(arg)
            self.graph_frame_count += 1

        self.update_xdot(no_zoom=(current_id == self.prev_graph_id))
        self.prev_graph_id = current_id

    def get_graph_id(self, edges):
        """If any of these quantities change, the graph should be redrawn."""
        node_ids = set()
        for edge in edges:
            node_ids.add(edge[0])
            node_ids.add(edge[1])
        # Get a set of ids that are actually present in the state summaries.
        # We need this in case of no-longer-purely-base-node cycle points.
        node_ids_in_state = set(node_ids).intersection(
            set(self.state_summary).union(set(self.fam_state_summary)))
        # Return a key that maps to the essential structure of the graph.
        return (set(edges), self.crop, node_ids_in_state,
                set(self.updater.filter_states_excl),
                self.updater.filter_name_string,
                self.orientation, self.ignore_suicide, self.subgraphs_on)
