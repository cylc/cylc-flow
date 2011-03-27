#!/usr/bin/env python

import gtk
import pygtk
####pygtk.require('2.0')
import time, os, re, sys
from warning_dialog import warning_dialog

class textload(object):
    def __init__( self, name, file ):
        self.name = name
        self.file = file
        
        self.find_current = None
        self.find_current_iter = None
        self.search_warning_done = False

        self.logview = gtk.TextView()
        self.logview.set_editable( False )

        searchbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect( "activate", self.enter_clicked, self.logview )
        searchbox.pack_start (entry, True)
        b = gtk.Button ("Find Next")
        b.connect_object ('clicked', self.on_find_clicked, self.logview, entry)
        searchbox.pack_start (b, False)

        self.hbox = gtk.HBox()

        sw = gtk.ScrolledWindow()
        #sw.set_border_width(5)
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( self.logview )
        self.logview.set_border_width(5)
        self.logview.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#fff" ))

        self.vbox = gtk.VBox()

        self.log_label = gtk.Label( self.file )
        self.log_label.modify_fg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#00a" ))
        self.vbox.pack_start( self.log_label, False )

        self.vbox.pack_start( sw, True )
        self.vbox.pack_start( searchbox, False )
        self.vbox.pack_start( self.hbox, False )

        # read file
        foo = open( self.file, 'rb' )
        lines = foo.readlines()
        foo.close()

        # load into text buffer
        tb = self.logview.get_buffer()
        for line in lines:
            tb.insert( tb.get_end_iter(), line )

        self.logview.scroll_to_iter( tb.get_start_iter(), 0 )

    def get_widget( self ):
        return self.vbox

    def quit_w_e( self, w, e ):
        pass

    def quit( self ):
        pass
 
    def enter_clicked( self, e, tv ):
        self.on_find_clicked( tv, e )

    def on_find_clicked( self, tv, e ):
        needle = e.get_text ()
        if not needle:
            return

        tb = tv.get_buffer ()

        if needle == self.find_current:
            s = self.find_current_iter
        else:
            s,e = tb.get_bounds()
            tb.remove_all_tags( s,e )
            s = tb.get_start_iter()
            tv.scroll_to_iter( s, 0 )
        try:
            f, l = s.forward_search (needle, gtk.TEXT_SEARCH_TEXT_ONLY) 
        except:
            warning_dialog( '"' + needle + '"' + " not found" ).warn()
        else:
            tag = tb.create_tag( None, background="#70FFA9" )
            tb.apply_tag( tag, f, l )
            self.find_current_iter = l
            self.find_current = needle
            tv.scroll_to_iter( f, 0 )


