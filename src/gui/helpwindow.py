#!/usr/bin/env python

import gtk
import pango

class helpwindow( object ):
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
        quit_button = gtk.Button( "Close" )
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

        self.tag_grey = self.tb.create_tag( None, foreground = "grey" )
        self.tag_red = self.tb.create_tag( None, foreground = "red" )
        self.tag_blue = self.tb.create_tag( None, foreground = "blue" )
        self.tag_green = self.tb.create_tag( None, foreground = "green" )
        self.tag_bold = self.tb.create_tag( None, weight = pango.WEIGHT_BOLD )

        self.add_main_heading( title )
         
    def add_main_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_bold, self.tag_red )

    def add_heading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n\n' + text, self.tag_bold, self.tag_blue )
 
    def add_subheading( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n    ' + text, self.tag_bold, self.tag_green )

    def add_text( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_grey )
 
    def add_text_bold( self, text ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), text, self.tag_grey, self.tag_bold )

    def add_list_item( self, item ):
        self.tb.insert_with_tags( self.tb.get_end_iter(), '\n o ' + item, self.tag_grey )

    def show( self ):
        self.window.show_all()

##########
def main( b ):
    help = helpwindow( "Gcylc Main Window Help" )
    help.add_heading( "\nOverview" )
    help.add_text( 
            "The gcylc main window shows your registered suites. Using " 
            "the available buttons and right-click menu choices you can "
            "register new suites; copy, rename, and unregister existing "
            "ones; start suites running or connect to ones that are "
            "already running; edit, search, validate, or graph suite "
            "definitions; and import suites from or export them to the "
            "central suite registration database (seen be all users). You "
            "can't run suites directly from the central database, but you "
            "can view, search, and graph them when considering whether to "
            "import them to your local database for your own use." )

    help.add_heading( "Buttons" )
    help.add_subheading( "Switch To Local/Central DB" )
    help.add_text(
            "Toggle between the local "
            "and central suite registration databases. Right-"
            "click menu options vary somewhat according to which "
            "database is being viewed." )
    help.add_subheading( "Filter" )
    help.add_text(
            "Use group and name match patterns to filter which suites "
            "are visisble." ) 
    help.add_subheading( "Register Another Suite" )
    help.add_text(
            "Open a file chooser dialog to load cylc suite definition "
            "(suite.rc) files and thereby register a new suite.") 
    help.add_subheading( "Quit" )
    help.add_text(
            "This quits the application but does not close down any "
            "suite editing or control windows, etc., that you have "
            "opened.") 

    help.add_heading( "Right Click Menu Options" )
    help.add_text(
            "Each menu option, except Control, launches one of the cylc "
            "commandline programs  inside a wrapper that captures command "
            "output in real time for display in a GUI window. The Control "
            "option launches a self-contained GUI application for suite "
            "control and montoring." )
    help.add_text_bold( "To operate on a whole group of suites" )
    help.add_text(" (some options only), click on any one of the "
            "group members and set 'Apply To Parent Group' or similar in "
            "the subsequent option popup window (you will be able to select "
            "the group itself when gcylc changes to tree-view registration display)." )
    help.add_subheading( "Control" )
    help.add_text(
            "Launch a suite control GUI to start a suite running "
            "or connect to a suite that is already running.") 
    help.add_subheading( "Edit" )
    help.add_text(
            "Edit the suite config (suite.rc) file") 
    help.add_subheading( "Graph" )
    help.add_text(
            "Graph the suite. The graph will update in real time "
            "as you edit the suite.") 
    help.add_subheading( "Search" )
    help.add_text(
            "Search in the suite config file and bin directory.") 
    help.add_subheading( "Validate" )
    help.add_text(
            "Parse the suite config file, validate it against the "
            "spec, and report any errors.") 
    help.add_subheading( "Copy" )
    help.add_text(
            "Copy an existing suite and register it for use.") 
    help.add_subheading( "Rename" )
    help.add_text(
            "Reregister an existing suite under a different group:name.") 
    help.add_subheading( "Export" )
    help.add_text(
            "Export a suite to the central database to make it available "
            "to others.") 
    help.add_subheading( "Unregister" )
    help.add_text(
            "Unregister a suite (note this does not delete the suite "
            "definition directory).") 
    help.show()

def filter( b ):
    help = helpwindow( "Filter Window Help" )
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
 
