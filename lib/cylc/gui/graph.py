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

import gobject
#import pygtk
#pygtk.require('2.0')
import gtk

from cylc.cycle_time import ct, CycleTimeError
from cylc.config import config, SuiteConfigError
from gcapture import gcapture, gcapture_tmpfile
from warning_dialog import warning_dialog

def graph_suite_popup( reg, cmd_help, defstartc, defstopc, graph_opts,
                       gcapture_windows, tmpdir, template_opts, parent_window=None ):
    """Popup a dialog to allow a user to configure their suite graphing."""
    try:
        import xdot
    except Exception, x:
        warning_dialog( str(x) + "\nGraphing disabled.", parent_window ).warn()
        return False

    window = gtk.Window()
    window.set_border_width(5)
    window.set_title( "Plot Suite Dependency Graph")
    window.set_transient_for( parent_window )
    window.set_type_hint( gtk.gdk.WINDOW_TYPE_HINT_DIALOG )

    vbox = gtk.VBox()

    label = gtk.Label("SUITE: " + reg )

    label = gtk.Label("[output FILE]" )
    outputfile_entry = gtk.Entry()
    hbox = gtk.HBox()
    hbox.pack_start( label )
    hbox.pack_start(outputfile_entry, True) 
    vbox.pack_start( hbox )

    cold_rb = gtk.RadioButton( None, "Cold Start" )
    cold_rb.set_active( True )
    warm_rb = gtk.RadioButton( cold_rb, "Warm Start" )
    hbox = gtk.HBox()
    hbox.pack_start (cold_rb, True)
    hbox.pack_start (warm_rb, True)
    vbox.pack_start( hbox, True )

    label = gtk.Label("[START]: " )
    start_entry = gtk.Entry()
    start_entry.set_max_length(14)
    if defstartc:
        start_entry.set_text( str(defstartc) )
    ic_hbox = gtk.HBox()
    ic_hbox.pack_start( label )
    ic_hbox.pack_start(start_entry, True) 
    vbox.pack_start(ic_hbox)

    label = gtk.Label("[STOP]:" )
    stop_entry = gtk.Entry()
    stop_entry.set_max_length(14)
    if defstopc:
        stop_entry.set_text( str(defstopc) )
    fc_hbox = gtk.HBox()
    fc_hbox.pack_start( label )
    fc_hbox.pack_start(stop_entry, True) 
    vbox.pack_start (fc_hbox, True)

    igsui_cb = gtk.CheckButton( "Ignore suicide triggers" )
    vbox.pack_start( igsui_cb, True )

    cancel_button = gtk.Button( "_Close" )
    cancel_button.connect("clicked", lambda x: window.destroy() )
    ok_button = gtk.Button( "_Graph" )
    ok_button.connect(
              "clicked",
              lambda w: graph_suite( reg, warm_rb.get_active(),
                                     igsui_cb,
                                     outputfile_entry.get_text(),
                                     start_entry.get_text(),
                                     stop_entry.get_text(),
                                     graph_opts,  gcapture_windows,
                                     tmpdir, template_opts, parent_window ) )

    help_button = gtk.Button( "_Help" )
    help_button.connect("clicked", cmd_help, 'prep', 'graph' )

    hbox = gtk.HBox()
    hbox.pack_start( ok_button, False )
    hbox.pack_end( cancel_button, False )
    hbox.pack_end( help_button, False )
    vbox.pack_start( hbox )

    window.add( vbox )
    window.show_all()


def graph_suite( reg, is_warm, igsui_cb, ofile, start, stop, graph_opts,
                 gcapture_windows, tmpdir, template_opts, window=None ):
    """Launch the cylc graph command with some options."""
    options = graph_opts
    if ofile != '':
        options += ' -o ' + ofile

    if True:
        if start != '':
            try:
                ct(start)
            except CycleTimeError,x:
                warning_dialog( str(x), window ).warn()
                return False
        if stop != '':
            if start == '':
                warning_dialog(
                        "You cannot override Final Cycle without " +
                        "overriding Initial Cycle.").warn()
                return False

            try:
                ct(stop)
            except CycleTimeError,x:
                warning_dialog( str(x), window ).warn()
                return False

    if is_warm:
        options += ' -w '

    if igsui_cb.get_active():
        options += ' -i '

    options += ' ' + reg + ' ' + start + ' ' + stop
    command = "cylc graph --notify-completion " + template_opts + " " + options
    foo = gcapture_tmpfile( command, tmpdir )
    gcapture_windows.append(foo)
    foo.run()
    return False
