#!/usr/bin/env python

from tailer import tailer
import gtk
import tempfile
import os, re, sys
from warning_dialog import warning_dialog, info_dialog
import subprocess
import helpwindow

# unit test: see the command $CYLC_DIR/bin/gcapture

class gcapture(object):
    """Run a command as a subprocess and capture its stdout and stderr
streams in real time to display in a GUI window. Examples:
    $ capture "echo foo"
    $ capture "echo hello && sleep 5 && echo bye"
Stderr is displayed in red.
    $ capture "echo foo && echox bar"
"""
    def __init__( self, command, stdoutfile, stderrfile, width=400, height=400, standalone=False ):
        self.standalone=standalone
        self.command = command
        self.stdout = stdoutfile
        self.stderr = stderrfile
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_border_width( 5 )
        self.window.set_title( 'subprocess output capture' )
        self.window.connect("delete_event", self.quit)
        self.window.set_size_request(width, height)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        self.textview = gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_wrap_mode( gtk.WRAP_WORD )

        tb = self.textview.get_buffer()
        self.blue = tb.create_tag( None, foreground = "darkblue" )
        self.red = tb.create_tag( None, foreground = "red" )
       
        tb.insert_with_tags( tb.get_end_iter(), command + '\n\n', self.blue )

        vbox = gtk.VBox()
        hbox = gtk.HBox()
        sw.add(self.textview)
        vbox.add(sw)

        save_button = gtk.Button( "_Save To File" )
        save_button.connect("clicked", self.save )

        close_button = gtk.Button( "_Close" )
        close_button.connect("clicked", self.quit, None, None )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.capture )

        hbox.pack_end(close_button, False)
        hbox.pack_end(help_button, False)

        hbox.pack_start( save_button, False )

        vbox.pack_start( hbox, False )
        self.window.add(vbox)
        close_button.grab_focus()
        self.window.show_all()

    def run( self ):
        proc = subprocess.Popen( self.command, stdout=self.stdout, stderr=self.stderr, shell=True )
        self.stdout_updater = tailer( self.textview, self.stdout.name, proc=proc, format=True )
        self.stdout_updater.start()
        self.stderr_updater = tailer( self.textview, self.stderr.name, proc=proc, tag=self.red )
        self.stderr_updater.start()

    def save( self, w ):
        tb = self.textview.get_buffer()
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
            warning_dialog( str(x) ).warn()
        else:
            f.write( txt )
            f.close()
            info_dialog( "Buffer saved to " + fname ).inform()

    def quit( self, w, e, data=None ):
        self.stdout_updater.quit = True
        self.stderr_updater.quit = True
        if self.standalone:
            gtk.main_quit()
        else:
            self.window.destroy()

class gcapture_tmpfile( gcapture ):
    def __init__( self, command, tmpdir, width=400, height=400, standalone=False ):
        stdout = tempfile.NamedTemporaryFile( dir = tmpdir )
        stderr = tempfile.NamedTemporaryFile( dir = tmpdir )
        gcapture.__init__(self, command, stdout, stderr, width, height, standalone )
 
