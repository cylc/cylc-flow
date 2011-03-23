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
    def __init__( self, command, stdoutfile, stderrfile, width=400, height=400, standalone=False, ignore_command=False ):
        self.standalone=standalone
        self.command = command
        self.ignore_command = ignore_command
        self.stdout = stdoutfile
        self.stderr = stderrfile
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_border_width( 5 )
        self.window.set_title( 'subprocess output capture' )
        self.window.connect("delete_event", self.quit)
        self.window.set_size_request(width, height)
        self.quit_already = False

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        sw2 = gtk.ScrolledWindow()
        sw2.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        self.textview = gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_wrap_mode( gtk.WRAP_WORD )

        self.textview2 = gtk.TextView()
        self.textview2.set_editable(False)
        self.textview2.set_wrap_mode( gtk.WRAP_WORD )

        tb = self.textview.get_buffer()
        tb2 = self.textview2.get_buffer()

        self.blue = tb.create_tag( None, foreground = "darkblue" )
        self.red = tb.create_tag( None, foreground = "red" )
       
        self.blue2 = tb2.create_tag( None, foreground = "darkblue" )
        self.red2 = tb2.create_tag( None, foreground = "red" )

        if not self.ignore_command:
            tb.insert_with_tags( tb.get_end_iter(), 'command: ' + command + '\n', self.blue )
            tb2.insert_with_tags( tb2.get_end_iter(), 'command: ' + command + '\n', self.blue2 )

        tb.insert_with_tags( tb.get_end_iter(), ' stdout: ' + stdoutfile.name + '\n', self.blue )
        tb2.insert_with_tags( tb2.get_end_iter(), ' stderr: ' + stderrfile.name + '\n\n', self.blue2 )


        vpanes = gtk.VPaned()
        # set pane position in pixels (otherwise top too small initially)
        vpanes.set_position(height/3)

        vbox = gtk.VBox()
        vbox2 = gtk.VBox()

        sw.add(self.textview)
        sw2.add(self.textview2)

        frame = gtk.Frame()
        frame.add(sw)
        vbox.add(frame)

        frame2 = gtk.Frame()
        frame2.add(sw2)
        vbox2.add(frame2)

        save_button = gtk.Button( "Save std_out" )
        save_button.connect("clicked", self.save, self.textview )
        save_button2 = gtk.Button( "Save std_err" )
        save_button2.connect("clicked", self.save, self.textview2 )

        hbox = gtk.HBox()
        hbox.pack_start( save_button, False )
        hbox.pack_start( save_button2, False )
        vbox.pack_start( hbox, False )

        close_button = gtk.Button( "_Close" )
        close_button.connect("clicked", self.quit, None, None )
        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.capture )

        hbox.pack_end(close_button, False)
        hbox.pack_end(help_button, False)

        # stderr on top
        vpanes.add( vbox2 )
        vpanes.add( vbox )

        self.window.add(vpanes)
        close_button.grab_focus()
        self.window.show_all()

    def run( self ):
        if not self.ignore_command:
            proc = subprocess.Popen( self.command, stdout=self.stdout, stderr=self.stderr, shell=True )
            self.stdout_updater = tailer( self.textview, self.stdout.name, proc=proc, format=True )
            self.stderr_updater = tailer( self.textview2, self.stderr.name, proc=proc, tag=self.red2 )
        else:
            self.stdout_updater = tailer( self.textview, self.stdout.name, format=True )
            self.stderr_updater = tailer( self.textview2, self.stderr.name, tag=self.red2 )
        self.stdout_updater.start()
        self.stderr_updater.start()

    def save( self, w, tv ):
        tb = tv.get_buffer()

        start = tb.get_start_iter()
        end = tb.get_end_iter()
        txt = tb.get_text( start, end )

        print txt

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
        if self.quit_already:
            # this is because gcylc currently maintains a list of *all*
            # gcapture windows, including those the user has closed.
            return
        self.stdout_updater.quit = True
        self.stderr_updater.quit = True
        self.quit_already = True
        if self.standalone:
            #print 'GTK MAIN QUIT'
            gtk.main_quit()
        else:
            #print 'WINDOW DESTROY'
            self.window.destroy()

class gcapture_tmpfile( gcapture ):
    def __init__( self, command, tmpdir, width=400, height=400, standalone=False ):
        stdout = tempfile.NamedTemporaryFile( dir = tmpdir )
        stderr = tempfile.NamedTemporaryFile( dir = tmpdir )
        gcapture.__init__(self, command, stdout, stderr, width, height, standalone )
