#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

from tailer import tailer
import gtk
import pango
import tempfile
import os, re, sys
from warning_dialog import warning_dialog, info_dialog
from util import get_icon
import subprocess
import helpwindow

# unit test: see the command $CYLC_DIR/bin/gcapture

class gcapture(object):
    """
Run a command as a subprocess and capture its stdout and stderr in real
time, to display in a GUI window. Examples:
    $ capture "echo foo"
    $ capture "echo hello && sleep 5 && echo bye"
Lines containing:
  'CRITICAL', 'WARNING', 'ERROR'
are displayed in red.
    $ capture "echo foo && echox bar"
    """
    def __init__( self, command, stdoutfile, width=400, height=400, standalone=False, ignore_command=False ):
        self.standalone=standalone
        self.command = command
        self.ignore_command = ignore_command
        self.stdout = stdoutfile
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_border_width( 5 )
        self.window.set_title( 'subprocess output capture' )
        self.window.connect("delete_event", self.quit)
        self.window.set_size_request(width, height)
        self.window.set_icon( get_icon() )
        self.quit_already = False

        self.find_current = None
        self.find_current_iter = None
        self.search_warning_done = False

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        self.textview = gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_wrap_mode( gtk.WRAP_WORD )
        # Use a monospace font. This is safe - by testing - setting an
        # illegal font description has no effect.
        self.textview.modify_font( pango.FontDescription("monospace") )
        tb = self.textview.get_buffer()

        self.blue = tb.create_tag( None, foreground = "darkblue" )
        self.ftag = tb.create_tag( None, background="#70FFA9" )

        self.warning_re = 'WARNING'
        self.critical_re = 'CRITICAL|ERROR'

        if not self.ignore_command:
            tb.insert_with_tags( tb.get_end_iter(), 'command: ' + command + '\n', self.blue )
        tb.insert_with_tags( tb.get_end_iter(),     'output : ' + stdoutfile.name + '\n\n', self.blue )

        vbox = gtk.VBox()
        sw.add(self.textview)

        frame = gtk.Frame()
        frame.add(sw)
        vbox.add(frame)

        save_button = gtk.Button( "Save As" )
        save_button.connect("clicked", self.save, self.textview )

        hbox = gtk.HBox()
        hbox.pack_start( save_button, False )

        self.freeze_button = gtk.ToggleButton( "_Disconnect" )
        self.freeze_button.set_active(False)
        self.freeze_button.connect("toggled", self.freeze )

        searchbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect( "activate", self.enter_clicked )
        searchbox.pack_start (entry, True)
        b = gtk.Button ("Find Next")
        b.connect_object ('clicked', self.on_find_clicked, entry)
        searchbox.pack_start (b, False)
        searchbox.pack_start( self.freeze_button, False )

        close_button = gtk.Button( "_Close" )
        close_button.connect("clicked", self.quit, None, None )
        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.capture )

        hbox.pack_end(close_button, False)
        hbox.pack_end(help_button, False)

        vbox.pack_start( searchbox, False )
        vbox.pack_start( hbox, False )

        self.window.add(vbox)
        close_button.grab_focus()
        self.window.show_all()

    def run( self ):
        if not self.ignore_command:
            self.proc = subprocess.Popen( self.command, stdout=self.stdout, stderr=subprocess.STDOUT, shell=True )
            self.stdout_updater = tailer( self.textview, self.stdout.name, proc=self.proc, warning_re=self.warning_re, critical_re=self.critical_re )
        else:
            self.stdout_updater = tailer( self.textview, self.stdout.name, warning_re=self.warning_re, critical_re=self.critical_re )
        self.stdout_updater.start()

    def freeze( self, b ):
        if b.get_active():
            self.stdout_updater.freeze = True
            b.set_label( '_Reconnect' )
        else:
            self.stdout_updater.freeze = False
            b.set_label( '_Disconnect' )

    def save( self, w, tv ):
        tb = tv.get_buffer()

        start = tb.get_start_iter()
        end = tb.get_end_iter()
        txt = tb.get_text( start, end )

        dialog = gtk.FileChooserDialog(title='Save As',
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                    gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        filter = gtk.FileFilter()
        filter.set_name("any")
        filter.add_pattern("*")
        dialog.add_filter( filter )

        response = dialog.run()

        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return False

        fname = dialog.get_filename()
        dialog.destroy()

        try:
            f = open( fname, 'wb' )
        except IOError, x:
            warning_dialog( str(x), self.window ).warn()
        else:
            f.write( txt )
            f.close()
            info_dialog( "Buffer saved to " + fname, self.window ).inform()

    def quit( self, w, e, data=None ):
        if self.quit_already:
            # this is because gcylc currently maintains a list of *all*
            # gcapture windows, including those the user has closed.
            return
        self.stdout_updater.quit = True
        self.quit_already = True
        if self.standalone:
            #print 'GTK MAIN QUIT'
            gtk.main_quit()
        else:
            #print 'WINDOW DESTROY'
            self.window.destroy()

    def enter_clicked( self, e ):
        self.on_find_clicked( e )

    def on_find_clicked( self, e ):
        tv = self.textview
        tb = tv.get_buffer ()
        needle = e.get_text()

        if not needle:
            s,e = tb.get_bounds()
            tb.remove_tag( self.ftag, s,e )
            return

        self.stdout_updater.freeze = True
        self.freeze_button.set_active(True)
        self.freeze_button.set_label('_Reconnect')
        if not self.search_warning_done:
            warning_dialog( "Find Next disconnects the live feed. Click Reconnect when you're done.",
                            self.window ).warn()
            self.search_warning_done = True

        if needle == self.find_current:
            s = self.find_current_iter
        else:
            s,e = tb.get_bounds()
            tb.remove_tag( self.ftag, s,e )
            s = tb.get_end_iter()
            tv.scroll_to_iter( s, 0 )
        try:
            f, l = s.backward_search(needle, gtk.TEXT_SEARCH_VISIBLE_ONLY) 
        except:
            warning_dialog( '"' + needle + '"' + " not found", self.window ).warn()
        else:
            tb.apply_tag( self.ftag, f, l )
            self.find_current_iter = f
            self.find_current = needle
            tv.scroll_to_iter( f, 0 )

class gcapture_tmpfile( gcapture ):
    def __init__( self, command, tmpdir, width=400, height=400, standalone=False ):
        stdout = tempfile.NamedTemporaryFile( dir = tmpdir )
        gcapture.__init__(self, command, stdout, width=width, height=height, standalone=standalone )
