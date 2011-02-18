import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re
import threading
from config import config
from port_scan import scan_my_suites
from registration import localdb, centraldb, RegistrationError
from gtkmonitor import monitor
from color_rotator import rotator

class chooser_updater(threading.Thread):
    def __init__(self, owner, regd_liststore, db, is_cdb, host, ownerfilt=[], groupfilt=[], namefilt=None ):
        self.ownerfilt = ownerfilt
        self.groupfilt = groupfilt
        self.namefilt = namefilt
        self.db = db
        self.is_cdb = is_cdb
        self.owner = owner
        self.quit = False
        self.host = host
        self.regd_liststore = regd_liststore
        super(chooser_updater, self).__init__()
        self.running_choices = []
        self.regd_choices = []
        self.line_colors = rotator([ '#ccc', '#aaa' ])
        self.state_line_colors = rotator([ '#fcc', '#faa' ])
    
    def run( self ):
        while not self.quit:
            if self.running_choices_changed() or self.regd_choices_changed():
                gobject.idle_add( self.update_liststore )
            time.sleep(1)
        else:
            pass
    
    def running_choices_changed( self ):
        # (name, owner, port)
        suites = scan_my_suites( self.host )
        if suites != self.running_choices:
            self.running_choices = suites
            return True
        else:
            return False

    def regd_choices_changed( self ):
        regs = self.db.get_list( self.ownerfilt, self.groupfilt, self.namefilt ) 
        if regs != self.regd_choices:
            self.regd_choices = regs
            return True
        else:
            return False

    def update_liststore( self ):
        # it is expected that a single user will not have a huge number
        # of suites, and registrations will change infrequently,
        # so just clear and recreate the list rather than 
        # adjusting element-by-element.
        ##print "Updating list of available suites"
        ports = {}
        for suite in self.running_choices:
            name, port = suite
            ports[ name ] = port

        self.regd_liststore.clear()
        choices = self.regd_choices
        for reg in choices:
            col = self.line_colors.get_color()
            grn = '#2f2'
            #red = '#ff1a45'
            red = self.state_line_colors.get_color()
            name, suite_dir, descr = reg
            suite_dir = re.sub( os.environ['HOME'], '~', suite_dir )
            if self.is_cdb:
                self.regd_liststore.append( [name, col, '(cdb)', red, suite_dir, col, descr, col ] )
            else:
                if name in ports:
                    self.regd_liststore.append( [name, grn, 'port ' + str(ports[name]), '#19ae0a', suite_dir, grn, descr, grn ] )
                else:
                    self.regd_liststore.append( [name, col, 'dormant', red, suite_dir, col, descr, col ] )

class chooser(object):
    def __init__(self, host, imagedir, readonly=False ):
        self.updater = None
        self.filter_window = None
        self.owner = os.environ['USER']
        self.readonly = readonly

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if self.readonly:
            self.window.set_title("cylc view (READONLY)" )
        else:
            self.window.set_title("cylc control" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(600, 200)
        #self.window.set_size_request(400, 100)
        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        regd_treeview = gtk.TreeView()
        # suite, state, title, colors...
        self.regd_liststore = gtk.ListStore( str, str, str, str, str, str, str, str, )
        regd_treeview.set_model(self.regd_liststore)

        # Start updating the liststore now, as we need values in it
        # immediately below (it may be possible to delay this till the
        # end of __init___() but it doesn't really matter.
        self.cdb = False # start with local reg db
        self.start_updater()

        regd_ts = regd_treeview.get_selection()
        regd_ts.set_mode( gtk.SELECTION_SINGLE )
        regd_ts.set_select_function( self.get_selected_suite, self.regd_liststore )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Suite', cr, text=0, background=1 )
        regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'State', cr, text=2, background=3 ) # use background color stored in col 3
        regd_treeview.append_column( tvc ) 

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Title', cr, text=6, background=5 )
        regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Definition', cr, text=4, background=7 )
        regd_treeview.append_column( tvc )

        # NOTE THAT WE CANNOT LEAVE ANY VIEWER WINDOWS OPEN WHEN WE
        # CLOSE THE CHOOSER WINDOW because when launched by the chooser 
        # they are all under the same gtk main loop (?) and do not
        # call gtk_main.quit() unless launched as standalone viewers.
        quit_all_button = gtk.Button( "Close All Windows" )
        quit_all_button.connect("clicked", self.delete_all_event, None, None )

        db_button = gtk.Button( "Local/Central DB" )
        db_button.connect("clicked", self.switchdb, None, None )

        filter_button = gtk.Button( "Filter" )
        filter_button.connect("clicked", self.filter_popup, None, None )

        vbox = gtk.VBox()
        sw.add( regd_treeview )
        vbox.pack_start( sw, True )

        hbox = gtk.HBox()
        hbox.pack_start( quit_all_button, False )
        hbox.pack_start( db_button, False )
        hbox.pack_start( filter_button, False )

        vbox.pack_start( hbox, False )

        self.window.add(vbox)
        self.window.show_all()

        self.viewer_list = []

    def start_updater(self, ownerfilt=[], groupfilt=[], namefilt=None):
        if self.cdb:
            db = centraldb()
        else:
            db = localdb()
        if self.updater:
            self.updater.quit = True # does this take effect?
        self.updater = chooser_updater( self.owner, self.regd_liststore, db, self.cdb, self.host, ownerfilt, groupfilt, namefilt )
        self.updater.update_liststore()
        self.updater.start()

    def filter(self, w, owner_e, group_e, name_e ):
        ownerfilt = [ owner_e.get_text() ]
        groupfilt = [ group_e.get_text() ]
        namefilt = name_e.get_text()
        self.start_updater( ownerfilt, groupfilt, namefilt )

    def filter_reset(self, w, owner_e, group_e, name_e ):
        if self.cdb:
            owner_e.set_text('')
        group_e.set_text('')
        name_e.set_text('')
        self.start_updater()

    def filter_popup(self, w, e, data=None):
        self.filter_window = gtk.Window()
        self.filter_window.set_border_width(5)
        self.filter_window.set_title( "Filter Suite Registration Database" )

        vbox = gtk.VBox()

        box = gtk.HBox()
        label = gtk.Label( 'Owner' )
        box.pack_start( label, True )
        owner_entry = gtk.Entry()
        if not self.cdb:
            owner_entry.set_text( self.owner )
            owner_entry.set_sensitive( False )
        box.pack_start (owner_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: self.filter_window.destroy() )

        apply_button = gtk.Button( "Apply" )
        apply_button.connect("clicked", self.filter, owner_entry, group_entry, name_entry )

        reset_button = gtk.Button( "Reset" )
        reset_button.connect("clicked", self.filter_reset, owner_entry, group_entry, name_entry )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.filter_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_start( cancel_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        self.filter_window.add( vbox )
        self.filter_window.show_all()

    def switchdb( self, w, e, data=None ):
        if self.filter_window:
            self.filter_window.destroy()
        self.cdb = not self.cdb
        self.start_updater()

    def delete_all_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def get_selected_suite( self, selection, treemodel ):
        if self.cdb:
            return

        iter = treemodel.get_iter( selection )

        name = treemodel.get_value( iter, 0 )
        suite_dir = treemodel.get_value( iter, 1 )
        state = treemodel.get_value( iter, 2 ) 

        m = re.match( 'RUNNING \(port (\d+)\)', state )
        port = None
        if m:
            port = m.groups()[0]

        # get suite logging directory
        logging_dir = os.path.join( config(name)['top level logging directory'], name ) 

        tv = monitor(name, self.owner, self.host, port, suite_dir, logging_dir, self.imagedir, self.readonly )
        self.viewer_list.append( tv )
        return False
