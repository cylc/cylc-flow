#!/usr/bin/env python

import os
import gtk
import time
import pango
import subprocess

class launcher:
    def __init__(self ):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("HPCF Ministerial Launch Button" )
        window.set_size_request(400, 400)
        window.connect("delete_event", self.quit )
        window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#def" ))

        hbox = gtk.HBox()
        vbox = gtk.VBox()
        quit_button = gtk.Button( "HPCF\nOperation\nSTART" )
        quit_button.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#acf" ))
        quit_button.modify_bg( gtk.STATE_PRELIGHT, gtk.gdk.color_parse( "#36a" ))
        label = quit_button.child
        label.modify_font( pango.FontDescription( "sans 38" ))
        label.modify_fg(  gtk.STATE_NORMAL, gtk.gdk.color_parse( "#008" ))
        label.set_justify( gtk.JUSTIFY_CENTER )

        quit_button.connect("clicked", self.launch_and_quit, None, None )
        vbox.pack_start( quit_button, expand=True, padding=50 )
        hbox.pack_start( vbox, True, padding=50 )
        window.add( hbox )
        window.show_all()

    def quit( self, w, e, data=None ):
        gtk.main_quit()

    def launch_and_quit( self, w, e, data=None ):

        command = "/usr/local/bin/ministerial-opening &"
        res = subprocess.call( command, shell=True )

        #time.sleep(2)

        command = "cylc start -d oper 2010072206 &"
        res = subprocess.call( command, shell=True )

        time.sleep(2)

        gtk.main_quit()

if __name__ == "__main__":
    app = launcher()
    gtk.main()
