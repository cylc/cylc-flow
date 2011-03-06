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
        self.tag_title = self.tb.create_tag( None, foreground = "#003" )
        self.tag_heading = self.tb.create_tag( None, foreground = "#008" )
        self.tag_subheading = self.tb.create_tag( None, foreground = "#00f" )
        self.tag_bold = self.tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.add_main_heading( title )
        quit_button.grab_focus()
         
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
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n o ', self.tag_bold )
        self.tb.insert_with_tags( self.tb.get_end_iter(), item, self.tag_text )

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

The gcylc main window initially shows your privately registered suites.

Using the available buttons and right-click menu items you can register
new suites; copy, reregister, and unregister existing suites; start
suites running or connect a controller to suites that are already
running; edit, search, validate, and graph suite definitions; and import
suites from, or export them to, the central suite registration database
(which is seen by all users). You can't run suites directly from the
central database (they may be owned by others after all) but you can
view, search, validate, and graph them when considering whether to
import them for your own use.

%h2 Buttons

%h3 Switch To Local/Central DB

Toggle between the local and central suite registration databases.

%h3 Filter

Change which suites are visible by searching on group and name match
patterns.

%h3 Register Another Suite

Open a file chooser dialog to load a cylc suite definition (suite.rc)
file and thereby register a suite.

%h3 Quit

This quits the application but does not close down any suite editing or
control windows, etc., that you have opened.

%h2 Right Click Menu Options

Each right-click menu item runs a subprocess inside a GUI wrapper that
captures stdout and stderr for display in real time. The output log
window can be closed without affecting the associated subprocess (but
you will lose access to the output). The Control subprocess is a
self-contained GUI application for suite control and montoring, while
the others are cylc commandline programs. The options available depend
on whether you have right-clicked on a suite or a group of suites.

%h3 Control

Launch a suite control GUI to start a suite running, or connect to a
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

%h3 Export

Export a suite to the central database to make it available to others.

%h3 Import

Import a suite from the central database, to modify and use yourself.

%h3 Reregister

Reregister an existing suite under a different group:name.

%h3 Unregister

Unregister a suite (this does not delete the suite definition directory).""")
    help.show()

def filter( b ):
    help = helpwindow( "Filter Window Help", """
Change suite visibility by filtering on group and/or name with
(Python-style) regular expressions (so, for example, the
wildcard is '.*, not '*' as in a shell glob expression).

Filter patterns have an implicit string start character ('^') but
no implicit string end character ('$'). Examples:

%i foo - matches 'foo' and 'foobar', but not 'barfoo'
%i foo$ - matches 'foo' only
%i .*foo$  - matches 'foo', 'barfoo', but not 'foobar'
%i (?i)foo - case-insensitive (matches 'foo', 'Food', 'FOOb',...)
%i (foo|bar) - match 'foo' or 'bar' followed by anything""")
    help.show()

def edit( b ):
    help = helpwindow( "Edit Window Help", """
By default ('Edit') this changes the current working directory to
your suite definition directory (so that you can easily open include 
files and suite bin scripts) and spawns your $EDITOR on the suite.rc
file.

Choosing 'Edit Inlined' lets you edit a copy of the suite.rc file with
all include-files inlined; changes will be split back out into the
include files when you exit from the editor (see 'cylc prep edit --help'
for more information).

Note that for gcylc, as opposed to the command line 'cylc edit', you
must use a GUI editor such as emacs or gvim, or else run your editor in
a terminal:
%i export EDITOR=emacs
%i export EDITOR=xemacs
%i export EDITOR='gvim -f'       # (*) see below
%i export EDITOR='xterm -e vim'  # run vim in a new xterminal

(*) The '-f' option is required to prevent gvim detaching from the
parent process, which is important for inlined editing (the parent 
process has to know when you exit from the editor).
""")
    help.show()
 
