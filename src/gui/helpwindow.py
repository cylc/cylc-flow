#!/usr/bin/env python

import re
import gtk
import pango
import string
from color_rotator import rotator

class helpwindow_base( object ):
    def __init__( self, title, height=400 ):
        self.window = gtk.Window()
        #window.set_border_width( 10 )
        self.window.set_title( title )

        self.window.set_size_request(600, int(height))

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "_Close" )
        quit_button.connect("clicked", lambda x: self.window.destroy() )
        vbox.pack_start( sw )
        vbox.pack_start( quit_button, False )

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#def" ))
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
    def __init__( self, title, height, text ):
        helpwindow_base.__init__(self, title, height )
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
    help = helpwindow( "Gcylc Main Window Help", 500, """%h2 Overview

Gcylc initially shows your local (privately registered) suites. Using
the menu bar and right-click menu items you can register new suites;
copy, reregister, and unregister existing suites; start suites running
or connect a controller to suites that are already running; edit,
search, validate, and graph suite definitions; and import suites from,
or export them to, the central suite registration database (which is
seen by all users). You can also view, search, validate, and graph
suites in the central database when considering whether to import them
for your own use.

%h2 Menu Bar

%h3 File > New

Register another suite. This opens a file chooser dialog configured to
filter for cylc suite definition (suite.rc) files.

%h3 File > Exit

This quits the application but does not close down any suite editing or
control windows, etc., that you have opened.

%h3 View > Filter

Change which suites are visible by searching on group and name match
patterns.

%h3 View > Expand

Expand the registration database treeview.

%h3 View > Collapse

Collapse the registration database treeview.

%h3 View > LocalDB

View the local (user-specific) suite registration database.

%h3 View > CentralDB

View the central (all users) suite registration database.


%h2 Right Click Menu Options

The Right-Click menu options available depend on whether you have
clicked on a running suite, a dormant suite, or a group of suites.  For
options relating to suite registration, registration groups are created
and deleted as required (you don't need to explicitly create group 'foo'
before registering a suite 'foo:bar', for example).

Each right-click menu item invokes a subprocess inside a wrapper that
captures the stdout and stderr streams for display in a log window that
updates in real time. These output log windows can be closed without
affecting the associated subprocess, but you will lose access to the
output. The Control option invokes a self-contained GUI application for
suite control and montoring (like 'gcylc SUITE') while the other options
invoke cylc commandline programs. If you start a suite from within a
control app you will see the suite stdout and stderr in the app's
log window; otherwise, if you just connect to a suite that is
already running, you won't. 

%h3 Control

Launch a control GUI to start a suite running, or to connect to a suite
that is already running. 

If you start the suite from within the control GUI, or if you connect to
a suite that was started from a control GUI, the GUI subprocess output
window will show suite stdout and stderr as redirected to the files
$HOME/.cylc/GROUP:NAME.(out|err).

If you start a suite from the commandline, however, stdout and stderr
will go to the terminal, or to any files you care to redirect to yourself.
Reconnecting to such a suite from a control GUI will not show this output.

%h3 View Output

This opens a new view of the suite stdout and stderr files
$HOME/.cylc/GROUP:NAME.(out|err) used when suites are started from
within gcylc (as opposed to the commandline) - useful if you closed 
the original output window that opens with a new instance of the control
GUI.

%h3 Dump

(Running suites only) Print the current state of each task in the suite.

%h3 Nudge

(Running suites only) Invoke the cylc task processing loop manually in 
order to update the estimated task "time till completion" intervals
shown in suite monitor windows.

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

%h3 Describe

Print the suite description.

%h3 List Tasks

Print the suite's configured task list.


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
    help = helpwindow( "Filter Help", 300, """
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
    help = helpwindow( "Edit Help", 400, """
By default ('Edit') this changes the current working directory to
your suite definition directory (so that you can easily open include 
files and suite bin scripts) and spawns your $GEDITOR on the suite.rc
file.

Choosing 'Edit Inlined' lets you edit a copy of the suite.rc file with
all include-files inlined; changes will be split back out into the
include files when you exit from the editor (see 'cylc prep edit --help'
for more information).

Note that for gcylc, as opposed to the command line 'cylc edit', you
must use a GUI editor such as emacs or gvim, or else run your editor in
a terminal:
%i export GEDITOR=emacs
%i export GEDITOR=xemacs
%i export GEDITOR='gvim -f'       # (*) see below
%i export GEDITOR='xterm -e vim'  # run vim in a new xterminal

If $GEDITOR is not defined, $EDITOR will be tried, but this will fail
if it is not a GUI editor or an in-terminal invocation as shown above.

(*) The '-f' option is required to prevent gvim detaching from the
parent process, which is important for inlined editing (the parent 
process has to know when you exit from the editor).
""")
    help.show()
 
def graph( b ):
    help = helpwindow( "Graph Help", 200, """
Plot the suite dependency graph.  The graph viewer will update in real
time if you edit the suite definition 'dependencies' or 'visualization'
sections.  If you enter an Output File name an image file, type
determined by file extension, will be written (and rewritten if the
graph changes). See 'cylc prep graph --help' for more information on
available file types.""")
    help.show()

def search( b ):
    help = helpwindow( "Search Help", 300, """
Search for matches to a (Python-style) regular expression in a suite
definition directory (i.e. suite.rc file and include-files, and any
scripts in the suite bin directory). Suite.rc matches are reported by
suite definition Section and filename  (in case of include-files).

Partial matches are allowed (i.e. there is no implicit string start
('^') or end ('$') character in the pattern. Examples:

%i foo - matches 'foo', 'foobar', 'barfoo', ...
%i ^foo$ - matches 'foo' only
%i (?i)foo - case-insensitive (matches 'foo', 'Food', 'bFOOb',...)
%i (foo|bar) - match 'foo' or 'bar' preceded or followed by anything""")
    help.show()

def copy( b ):
    help = helpwindow( "Copy Help", 200, """
Copy the defintion of a registered suite to the specified location and
register it under the new group:name. You can use environment variables
such as '$HOME' in the directory path. If you click 'Reference
Only' the suite definition will not be copied and the new registration
will point to the original suite.""")
    help.show()

def copy_group( b ):
    help = helpwindow( "Copy Group Help", 200, """
Copy an entire group of registered suites into sub-directories of the
specified location and register each group member under the new group
name. You can use environment variables such as '$HOME' in the directory
path. If you click 'Reference Only', the member suite definitions will
not be copied and the new registrations will point to the original suites.""")
    help.show()

def unregister( b ):
    help = helpwindow( "Unregister Help", 200, """
Delete a suite or group of suites from the registration database. Note
that this does not delete suite definition directories.""")
    help.show()

def reregister( b ):
    help = helpwindow( "Reregister Help", 200, """
Change the group and/or name (or group) under which a suite (or group of
suites) is registered.""")
    help.show()

def register( b ):
    help = helpwindow( "Register Help", 200, """
Register a suite under a given group and name. This has to be done
before you can run a suite, because all cylc commands refer to suites by
their registered group:name.""")
    help.show()

def importx( b ):
    help = helpwindow( "Import Help", 200, """
Import a suite (or group of suites) from the central database, making it
(or them) available to you to modify and use. The suite definition directory
will be copied from the registered location to the location your specify
here.  You can use environment variables such as '$HOME' in the directory
path.""")
    help.show()

def export( b ):
    help = helpwindow( "Export Help", 200, """
Export a suite (or group of suites) to the central database to make it
(or them) available to others.""")
    help.show()

def capture( b ):
    help = helpwindow( "Subprocess Capture Help", 200, """
This window captures stdout and stderr messages, in real time, from
subprocesses spawned by the gcylc GUI. You can close this window without
adversely affecting the subprocess itself, but if you do you will lose
access to the standard output streams.""")
    help.show()

def insertion( b ):
    help = helpwindow( "Insertion Help", 250, """
Insert the specified task or group into a running suite. Subsequent
behaviour of the inserted task(s), as for any task, depends entirely on
its type (a oneoff task will run once and not spawn a successor, and 
so on).  Task insertion groups are just a convenience to allow insertion
of multiple tasks at once (e.g. a handful of tasks required to cold
start part of a suite after certain problems have occured). These must
be defined in the suite.rc file [task insertion groups] section.""")
    help.show()
