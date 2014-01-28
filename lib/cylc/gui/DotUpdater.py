#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
from copy import deepcopy
import gobject
import gtk
import re
import string
import threading
from time import sleep


class DotUpdater(threading.Thread):

    def __init__(self, cfg, updater, treeview, info_bar, theme ):

        super(DotUpdater, self).__init__()

        self.quit = False
        self.cleared = True
        self.action_required = False
        self.autoexpand = True
        self.should_hide_headings = False
        self.should_group_families = ("dot" not in cfg.ungrouped_views)
        self.should_transpose_view = False
        self.is_transposed = False

        self.cfg = cfg
        self.updater = updater
        self.theme = theme
        self.info_bar = info_bar
        imagedir = self.cfg.imagedir
        self.last_update_time = None
        self.state_summary = {}
        self.fam_state_summary = {}
        self.ancestors_pruned = {}
        self.descendants = []
        self.filter = ""

        self.led_headings = []
        self.led_treeview = treeview
        self.led_liststore = treeview.get_model()
        self._prev_tooltip_task_id = None
        if hasattr(self.led_treeview, "set_has_tooltip"):
            self.led_treeview.set_has_tooltip(True)
            try:
                self.led_treeview.connect('query-tooltip',
                                          self.on_query_tooltip)
            except TypeError:
                # Lower PyGTK version.
                pass

        self.task_list = []

        # generate task state icons
        dotm = DotMaker( theme )
        self.dots = {}
        for state in task_state.legal:
            self.dots[ state ] = dotm.get_icon( state )
        self.dots['empty'] = dotm.get_icon()

        self.led_digits_one = []
        self.led_digits_two = []
        self.led_digits_blank = gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/one/digit-blank.xpm" )
        for i in range(10):
            self.led_digits_one.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/one/digit-" + str(i) + ".xpm" ))
            self.led_digits_two.append( gtk.gdk.pixbuf_new_from_file( imagedir + "/digits/two/digit-" + str(i) + ".xpm" ))

    def _set_tooltip(self, widget, tip_text):
        tip = gtk.Tooltips()
        tip.enable()
        tip.set_tip( widget, tip_text )

    def clear_list( self ):
        self.led_liststore.clear()
        # gtk idle functions must return false or will be called multiple times
        return False

    def update(self):
        if not self.updater.connected:
            if not self.cleared:
                gobject.idle_add(self.clear_list)
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
        self.ancestors_pruned = deepcopy(self.updater.ancestors_pruned)
        self.descendants = deepcopy(self.updater.descendants)

        if not self.should_group_families:
            self.task_list = deepcopy(self.updater.task_list)
        else:
            self.task_list = []

        self.updater.set_update(True)
        
        self.ctimes = []
        state_summary = {}
        state_summary.update(self.state_summary)
        state_summary.update(self.fam_state_summary)

        for id_ in state_summary:
            name, ctime = id_.split( TaskID.DELIM )
            if ctime not in self.ctimes:
                self.ctimes.append(ctime)
        self.ctimes.sort()

        if self.should_group_families:
            for key, val in self.ancestors_pruned.items():
                if key == 'root':
                    continue
                # highest level family name (or plain task) above root
                name = val[-2]
                if name not in self.task_list:
                    for ctime in self.ctimes:
                        if name + TaskID.DELIM + ctime in state_summary:
                            self.task_list.append( name )
                            break

        self.task_list.sort()
        if self.filter:
            try:
                self.task_list = [
                    t for t in self.task_list if \
                            self.filter in t or \
                            re.search( self.filter, t )]
            except:
                # bad regex (TODO - dialog warn from main thread - idle_add?)
                self.task_list = []
        return True

    def digitize( self, ctin ):
        # Digitize cycle time for the LED panel display.
        # For asynchronous tasks blank-pad the task tag.

        # TODO - if we ever have cycling modules for which minutes and
        # seconds are important, take the whole of ctin here:
        ncol = 10 # columns in the digital cycletime row
        ct = ctin[:ncol]
        led_ctime = []
        if len(ct) < ncol: # currently can't happen due to ctin[:ncol]
            zct = string.rjust( ct, ncol, ' ' ) # pad the string
        else:
            zct = ct
        for i in range( ncol ):
            digit = zct[i:i+1]
            if digit == ' ':
                led_ctime.append( self.led_digits_blank )
            elif i in [0,1,2,3,6,7]:
                led_ctime.append( self.led_digits_one[ int(digit) ] )
            else:
                led_ctime.append( self.led_digits_two[ int(digit) ] )

        return led_ctime

    def set_led_headings( self ):
        if self.should_transpose_view:
            new_headings = [ 'Name' ] + self.ctimes
        else:
            new_headings = ['Tag' ] + self.task_list
        if new_headings == self.led_headings:
            return False
        self.led_headings = new_headings
        tvcs = self.led_treeview.get_columns()
        labels = []
        for n in range( 1, len(self.led_headings) ):
            text = self.led_headings[n]
            tip = self.led_headings[n]
            if self.should_hide_headings:
                text = "..."
            label = gtk.Label(text)
            label.set_use_underline(False)
            label.set_angle(90)
            label.show()
            labels.append(label)
            label_box = gtk.VBox()
            label_box.pack_start( label, expand=False, fill=False )
            label_box.show()
            self._set_tooltip( label_box, tip )
            tvcs[n].set_widget( label_box )
        max_pixel_length = -1
        for label in labels:
            x, y = label.get_layout().get_size()
            if x > max_pixel_length:
                max_pixel_length = x
        for label in labels:
            while label.get_layout().get_size()[0] < max_pixel_length:
                label.set_text(label.get_text() + ' ')

    def ledview_widgets( self ):
    
        # this is how to set background color of the entire treeview to black:
        #treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#000' ) )

        if self.should_transpose_view:
            types = [str] + [gtk.gdk.Pixbuf] * len( self.ctimes )
            num_new_columns = len(types)
        else:
            types = [gtk.gdk.Pixbuf] * (10 + len( self.task_list)) + [str]
            num_new_columns = 1 + len(self.task_list)
        new_led_liststore = gtk.ListStore( *types )
        old_types = []
        for i in range(self.led_liststore.get_n_columns()):
            old_types.append(self.led_liststore.get_column_type(i))
        new_types = []
        for i in range(new_led_liststore.get_n_columns()):
            new_types.append(new_led_liststore.get_column_type(i))
        treeview_has_content = bool(len(self.led_treeview.get_columns()))
        
        if treeview_has_content and old_types == new_types:
            self.set_led_headings()
            self.led_liststore.clear()
            self.is_transposed = self.should_transpose_view
            return False

        # hardwired 10px lamp image width!
        lamp_width = 10

        self.led_liststore = new_led_liststore

        if (treeview_has_content and
                self.is_transposed == self.should_transpose_view):

            tvcs_for_removal = self.led_treeview.get_columns()[
                 num_new_columns:]
            
            for tvc in tvcs_for_removal:
                self.led_treeview.remove_column(tvc) 

            self.led_treeview.set_model(self.led_liststore)
            num_columns = len(self.led_treeview.get_columns())
            extra_columns = range(num_columns, num_new_columns)
            if self.is_transposed:
                extra_model_columns = extra_columns
            else:
                extra_model_columns = [9 + n for n in extra_columns]
            for model_col_num in extra_model_columns:
                # Add newly-needed columns.
                cr = gtk.CellRendererPixbuf()
                #cr.set_property( 'cell_background', 'black' )
                cr.set_property( 'xalign', 0 )
                tvc = gtk.TreeViewColumn( ""  )
                tvc.set_min_width( lamp_width )  # WIDTH OF LED PIXBUFS
                tvc.pack_end( cr, True )
                tvc.set_attributes( cr, pixbuf=model_col_num )
                self.led_treeview.append_column( tvc )
            self.set_led_headings()
            return False

        tvcs = self.led_treeview.get_columns()
        for tvc in tvcs:
            self.led_treeview.remove_column(tvc)

        self.led_treeview.set_model( self.led_liststore )

        if self.should_transpose_view:
            tvc = gtk.TreeViewColumn( 'Name' )
            cr = gtk.CellRendererText()
            tvc.pack_start( cr, False )
            tvc.set_attributes( cr, text=0 )
        else:
            tvc = gtk.TreeViewColumn( 'Task Tag' )
            for i in range(10):
                cr = gtk.CellRendererPixbuf()
                # cr.set_property( 'cell-background', 'black' )
                tvc.pack_start( cr, False )
                tvc.set_attributes( cr, pixbuf=i )
        
        self.led_treeview.append_column( tvc )

        if self.should_transpose_view:
            data_range = range(1, len( self.ctimes ) + 1)
        else:
            data_range = range(10, len( self.task_list ) + 10)
        for n in data_range:
            cr = gtk.CellRendererPixbuf()
            #cr.set_property( 'cell_background', 'black' )
            cr.set_property( 'xalign', 0 )
            tvc = gtk.TreeViewColumn( ""  )
            tvc.set_min_width( lamp_width )  # WIDTH OF LED PIXBUFS
            tvc.pack_end( cr, True )
            tvc.set_attributes( cr, pixbuf=n )
            self.led_treeview.append_column( tvc )
        self.set_led_headings()
        self.is_transposed = self.should_transpose_view

    def on_query_tooltip(self, widget, x, y, kbd_ctx, tooltip):
        """Handle a tooltip creation request."""
        tip_context = self.led_treeview.get_tooltip_context(x, y, kbd_ctx)
        if tip_context is None:
            self._prev_tooltip_task_id = None
            return False
        x, y = self.led_treeview.convert_widget_to_bin_window_coords(x, y)
        path, column, cell_x, cell_y = self.led_treeview.get_path_at_pos(x, y)
        col_index = self.led_treeview.get_columns().index(column)
        if self.is_transposed:
            iter_ = self.led_treeview.get_model().get_iter(path)
            name = self.led_treeview.get_model().get_value(iter_, 0)
            try:
                ctime = self.led_headings[col_index]
            except IndexError:
                # This can occur for a tooltip while switching from transposed.
                return False
            if col_index == 0:
                task_id = name
            else:
                task_id = name + TaskID.DELIM + ctime
        else:
            try:
                ctime = self.ctimes[path[0]]
            except IndexError:
                return False
            if col_index == 0:
                task_id = ctime
            else:
                try:
                    name = self.led_headings[col_index]
                except IndexError:
                    return False
                task_id = name + TaskID.DELIM + ctime
        if task_id != self._prev_tooltip_task_id:
            self._prev_tooltip_task_id = task_id
            tooltip.set_text(None)
            return False
        if col_index == 0:
            tooltip.set_text(task_id)
            return True
        text = get_id_summary( task_id, self.state_summary,
                               self.fam_state_summary, self.descendants )
        if text == task_id:
            return False
        tooltip.set_text(text)
        return True

    def update_gui( self ):
        #print "Updating GUI"
        new_data = {}
        state_summary = {}
        state_summary.update( self.state_summary )
        state_summary.update( self.fam_state_summary )
        self.ledview_widgets()

        tasks_by_ctime = {}
        tasks_by_name = {}
        for id_ in state_summary:
            name, ctime = id_.split( TaskID.DELIM )
            tasks_by_ctime.setdefault( ctime, [] )
            tasks_by_ctime[ctime].append(name)
            tasks_by_name.setdefault( name, [] )
            tasks_by_name[name].append(ctime)

        # flat (a liststore would do)
        names = tasks_by_name.keys()
        names.sort()
        tvcs = self.led_treeview.get_columns()

        if self.is_transposed:
            for name in self.task_list:
                ctimes_for_tasks = tasks_by_name.get( name, [] )
                if not ctimes_for_tasks:
                    continue
                state_list = [ ]
                for ctime in self.ctimes:
                    if ctime in ctimes_for_tasks:
                        state = state_summary[ name + TaskID.DELIM + ctime ][ 'state' ]
                        state_list.append( self.dots[state] )
                    else:
                        state_list.append( self.dots['empty'] )
                try:
                    self.led_liststore.append( [name] + state_list )
                except ValueError:
                    # A very laggy store can change the columns and raise this.
                    return False
        else:
            for ctime in self.ctimes:
                tasks_at_ctime = tasks_by_ctime[ ctime ]
                state_list = [ ]
                for name in self.task_list:
                    if name in tasks_at_ctime:
                        state = state_summary[ name + TaskID.DELIM + ctime ][ 'state' ]
                        try:
                            state_list.append( self.dots[state] )
                        except KeyError:
                            # unknown task state: use empty and save for next encounter
                            self.dots[state] = self.dots['empty']
                            state_list.append( self.dots['empty'] )
                    else:
                        state_list.append( self.dots['empty'] )
                try:
                    self.led_liststore.append( self.digitize( ctime ) +
                                               state_list + [ctime])
                except ValueError:
                    # A very laggy store can change the columns and raise this.
                    return False

        self.led_treeview.columns_autosize()
        return False

    def run(self):
        glbl = None
        states = {}
        while not self.quit:
            if self.update() or self.action_required:
                gobject.idle_add( self.update_gui )
                self.action_required = False
            sleep(0.2)
        else:
            pass
            ####print "Disconnecting task state info thread"

