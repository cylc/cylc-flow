#!/usr/bin/env python

import re
import gtk
import pango
import string

class helpwindow_base( object ):
    def __init__( self, title ):
        self.window = gtk.Window()
        #window.set_border_width( 10 )
        self.window.set_title( title )

        self.window.set_size_request(600, 600)

        #self.window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "_Close" )
        quit_button.connect("clicked", lambda x: self.window.destroy() )
        vbox.pack_start( sw )
        vbox.pack_start( quit_button, False )

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#fff" ))
        textview.set_editable( False )
        textview.set_wrap_mode( gtk.WRAP_WORD )
        sw.add( textview )
        self.window.add( vbox )
        self.tb = textview.get_buffer()

        self.tag_text = self.tb.create_tag( None, foreground = "#222" )
        self.tag_title = self.tb.create_tag( None, foreground = "blue" )
        self.tag_heading = self.tb.create_tag( None, foreground = "red" )
        self.tag_subheading = self.tb.create_tag( None, foreground = "#d73" )
        self.tag_bold = self.tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.add_main_heading( title )
         
    def add_main_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text + '\n', self.tag_bold, self.tag_title )

    def add_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n\n' + text + '\n', self.tag_bold, self.tag_heading )
 
    def add_subheading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n    ' + text, self.tag_bold, self.tag_subheading )

    def add_text( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_text )
 
    def add_text_bold( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_text, self.tag_bold )

    def add_list_item( self, item ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n o ' + item, self.tag_text )

    def show( self ):
        self.window.show_all()

class helpwindow( helpwindow_base ):
    def __init__( self, title, text ):
        helpwindow_base.__init__(self, title )
        self.parse( text )

    def parse( self, text ):
        def strip( line ):
            return re.sub( '%[\w\d]+ ', '', line )

        lines = string.split( text, '\n' )
        for line in lines:
            if re.match( '^%h1', line ):
                self.add_main_heading( strip(line) )
            elif re.match( '^%h2', line ):
                self.add_heading( strip(line) )
            elif re.match( '^%h3', line ):
                self.add_subheading( strip(line) )
            elif re.match( '^%b', line ):
                self.add_text_bold( strip(line ))
            elif re.match( '^%i', line ):
                self.add_list_item( strip(line ))
            else:
                self.add_text( line + ' ')

##########
def main( b ):
    help = helpwindow( "Gcylc Main Window Help", """%h2 Overview

The gcylc main window shows your registered suites. Using the available
buttons and right-click menu choices you can register new suites; copy,
rename, and unregister existing ones; start suites running or connect to
ones that are already running; edit, search, validate, or graph suite
definitions; and import suites from or export them to the central suite
registration database (seen be all users). You can't run suites directly
from the central database, but you can view, search, and graph them when
considering whether to import them to your local database for your own
use.

%h2 Buttons

%h3 Switch To Local/Central DB

Toggle between the local and central suite registration databases.
Right-click menu options vary somewhat according to which database is
being viewed.

%h3 Filter

Use group and name match patterns to filter which suites are visisble.

%h3 Register Another Suite

Open a file chooser dialog to load cylc suite definition (suite.rc)
files and thereby register a new suite.

%h3 Quit

This quits the application but does not close down any suite editing or
control windows, etc., that you have opened.

%h2 Right Click Menu Options

Each menu option, except Control, launches one of the cylc commandline
programs  inside a wrapper that captures command output in real time for
display in a GUI window. The Control option launches a self-contained
GUI application for suite control and montoring.
%b To operate on a whole group of suites
(some options only), click on any one of the group members and set
'Apply To Parent Group' or similar in the subsequent option popup window
(you will be able to select the group itself when gcylc changes to
tree-view registration display).  

%h3 Control

Launch a suite control GUI to start a suite running or connect to a
suite that is already running.

%h3 Edit

Edit the suite config (suite.rc) file

%h3 Graph

Graph the suite. The graph will update in real time as you edit the
suite.

%h3 Search

Search in the suite config file and bin directory.

%h3 Validate

Parse the suite config file, validate it against the spec, and report
any errors.

%h3 Copy

Copy an existing suite and register it for use.

%h3 Reregister

Reregister an existing suite under a different group:name.

%h3 Export

Export a suite to the central database to make it available to others.

%h3 Unregister

Unregister a suite (note this does not delete the suite definition directory).""")
    help.show()

def filter( b ):
    help = helpwindow_base( "Filter Window Help" )
    help.add_heading( "\nOverview" )
    help.add_text( 
            "Change suite registration visibility by filtering on "
            "group and/or name. Filter patterns can be plain strings "
            "or Python-style regular expressions (not the general "
            "regex wildcard is '.*' not '*'). Examples:")

    help.add_list_item( "OUTPUT_DIR - literal string" )
    help.add_list_item( "(?i)foo - case-insensitive (matches foo or Foo or FOO...)" )
    help.add_list_item( "(foo|bar) - match 'foo' or 'bar'" )
    help.show()
 

