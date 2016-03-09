#!/usr/bin/env python

"""
A wxPython gui to nsc (Pyro Name Server Control tool).
This gui doesn't have as many features as the xnsc that ships with Pyro,
but it has some nice features that the xnsc doesn't have ;)

'Pyro' - Python Remote Objects is
(c) Irmen de Jong - irmen@razorvine.net

This file 'wxnsc.py' is
(c) Jan Finell - finell@users.sourceforge.net


Usage (from the commandline):

# to use set PYRO environment variables or broadcasting
# for finding the nameserver host...
> wxnsc.py

"""

__author__   = "Jan Finell"
__date__     = "$Date: 2009/03/27 14:30:29 $"
__revision__ = "$Revision: 1.10.2.6 $"

#
# Standard modules
#
import os, sys, socket
import traceback, cStringIO

#
# GUI modules
#
import wx

#
# Pyro modules
#
from Pyro.naming import NameServerLocator
from Pyro.errors import NamingError, ConnectionClosedError,\
                        ConnectionDeniedError
import Pyro.core

#----------------------------------------------------------------------#
# Module constants
DEFAULT_GROUPNAME = ':Default'
PROTECTED_GROUPS  = [DEFAULT_GROUPNAME, ':Pyro']

GROUP_XPM = [
"16 16 9 1",
"       c None",
".      c #FFFFFF",
"+      c #000000",
"@      c #C3C3C3",
"#      c #A0A0A0",
"$      c #8080FF",
"%      c #585858",
"&      c #FFFFFF",
"*      c #808080",
"  +%+           ",
" +%$$++         ",
" +&%%$$+++++    ",
" +&&@%%$$$$$+   ",
" +&@&@@%$$$$%   ",
" +@&@@@@%%%%$+  ",
" +&@@@@@@@#@+$% ",
" +@@@@@@@#@#+$% ",
" +@@@#@@#@##+$% ",
" +@@@@@#@###+$% ",
" ++*@@#@####+$% ",
"   ++*@#####+$% ",
"     ++#####+$% ",
"       ++###+$++",
"         ++#+$++",
"           ++++ "]

GROUP_OPEN_XPM =[
"16 16 12 1",
"       c None",
".      c #FFFFFF",
"+      c #000000",
"@      c #8080FF",
"#      c #808080",
"$      c #C3C3C3",
"%      c #C0C0FF",
"&      c #A0A0A0",
"*      c #303030",
"=      c #FFFFFF",
"-      c #DCDCDC",
";      c #585858",
"    +++         ",
"    +@#++       ",
"    +@%@#++++   ",
"+++ +@%%%%%%@+  ",
"+&&*;@@@%%%%%@+ ",
"+#&&&#@@@@%%%@#+",
" *&&&&##@@@@%@#+",
" +#&&$$&##@@@@#+",
"  *&$&$$$$##@@#+",
"  +#$$$$-$-&@@#+",
"   *#-$$$-=%;@#+",
"    +*&--===&@#+",
"      +*$===%;#+",
"        +*$==##+",
"          +*$=#+",
"            +**+"]

ITEM_XPM = [
"16 16 11 1",
"       c None",
".      c #FFFFFF",
"+      c #FFFFFF",
"@      c #000000",
"#      c #585858",
"$      c #DCDCDC",
"%      c #FFFFC0",
"&      c #FFDCA8",
"*      c #303030",
"=      c #C3C3C3",
"-      c #A0A0A0",
"    #####**@@   ",
"    #$$$$$=*=@  ",
"    #$+++++#+$@ ",
"    #$+++++#$+=@",
"    #$+++++###*@",
"    #$++++++$=-@",
"    #$++++++%+$@",
"    #$+++++++++@",
"    #$++++%+%+%@",
"    #$+++++++&+@",
"    #$++%+%+%+%@",
"    #$+++++&+&+@",
"    #$%+%+%+%+%@",
"    #$+++&+&+&%@",
"    #$%+%+%+%%%@",
"    *@@@@@@@@@@@"]
#----------------------------------------------------------------------#
# Helper functions

def cmp_name(n1, n2):
   return cmp(n1[0], n2[0])

def show_message_dialog(parent, msg, title, style):
   if sys.platform[:3] == 'win':
      dlg = WinMessageDialog(parent, msg, title, style)
   else:
      dlg = wx.MessageDialog(parent, msg, title, style)
   dlg.CentreOnParent()
   retval = dlg.ShowModal()
   dlg.Destroy()
   return retval

#----------------------------------------------------------------------#
## Classes


class wx_StdoutLog(wx.TextCtrl):
   """
   :Purpose: A simple text ctrl that can be used for logging standard out
   """
   def write(self, data):
      if data.strip():
         wx.TextCtrl.AppendText(self, '%s\n' % data)

class wx_NSC(wx.Frame):
   """
   :Purpose: The main frame of the GUI.
   """
   def __init__(self, nsHost, nsPort, bcAddr):
      """
      :Parameters:
         - `nsHost`: the name server host to connect to. This is the
                     name of the host or the ip.
         - `nsPort`: the name server port. By default the Pyro name
                     server port is 9090
         - `bcAddr`: override for the broadcast address.
      """
      wx.Frame.__init__(self, None, -1, 'Pyro Name Server')
      self.nsHost           = nsHost
      self.nsPort           = nsPort
      self.bcAddr           = bcAddr
      self.NS               = None

      self._build()
      imageList = wx.ImageList(16,16)
      self.__idGroup = imageList.Add(wx.BitmapFromXPMData(GROUP_XPM))
      self.__idItem  = imageList.Add(wx.BitmapFromXPMData(ITEM_XPM))
      self.__idGroupOpen = imageList.Add(wx.BitmapFromXPMData(GROUP_OPEN_XPM))
      self.treeCtrlItems.SetImageList(imageList)
      self.__imageList = imageList

      self._bindEvents()
      # binding stdout to my own txtCtrl Log.
      sys.stdout = self.txtCtrlLog
      
      self._log("Pyro version: "+Pyro.constants.VERSION)
      
      self.nsc_findNS()
      if self.NS: self.update()
      
   #-- public methods --#      
   def enable(self, enable=True):
      """
      Enabling/disabling some of the buttons.
      """
      self.buttonDeleteGroup.Enable(enable)
      self.buttonCreateGroup.Enable(enable)
      self.buttonDeleteSelected.Enable(enable)
      self.buttonRegisterItem.Enable(enable)
      self.buttonShowMeta.Enable(enable)
      self.buttonSetMeta.Enable(enable)

   def update(self):
      """
      """
      tree = self.treeCtrlItems
      tree.DeleteAllItems()
      root = tree.AddRoot(':')
      tree.SetItemImage(root, self.__idGroup)
      tree.SetItemImage(root, self.__idGroupOpen,
                        wx.TreeItemIcon_Expanded)
      self._populate_tree(tree, root, ':')

      # enabling/disabling buttons, depending on the current state.
      self.enable(self.NS != None)      
      
   def _populate_tree(self, tree, parent, group):
      subgroupsL = self.nsc_list_groups(group)
      subgroupsL.sort()
      itemsL     = self.nsc_list_items(group)
      itemsL.sort()
      for subgroup in subgroupsL:
         groupB = tree.AppendItem(parent, subgroup)
         tree.SetPyData(groupB, 0)
         tree.SetItemImage(groupB, self.__idGroup)
         tree.SetItemImage(groupB, self.__idGroupOpen,
                           wx.TreeItemIcon_Expanded)
         self._populate_tree(tree, groupB, subgroup)
      for item in itemsL:
         itemB = tree.AppendItem(parent, item)
         tree.SetPyData(itemB, 1)
         tree.SetItemImage(itemB, self.__idItem)
         tree.SetItemImage(itemB, self.__idItem,
                           wx.TreeItemIcon_Selected)
   #-- nsc methods --#
   def nsc_findNS(self, ident=None):
      """
      Locating the Name Server by using given nsHost and nsPort
      """
      locator = NameServerLocator(identification=ident)
      try:
         if self.nsHost:
            self._log('connecting to Name Server (%s:%s)' % (self.nsHost,
                                                             self.nsPort))
            self.NS = locator.getNS(self.nsHost, self.nsPort, trace=1, bcaddr=self.bcAddr)
         else:
            self._log('broadcasting to find Name Server')
            self.NS = locator.getNS(None, None, trace = 1, bcaddr=self.bcAddr) 
            self.nsHost = self.NS.URI.address
            self.nsPort = self.NS.URI.port
         self.NS._setIdentification(ident)
         self._log('Name Server found, URI = %s' % self.NS.URI)
         self._setNSData()
      except ConnectionDeniedError, e:
         if str(e).find( Pyro.constants.deniedReasons[Pyro.constants.DENIED_SECURITY] ) != -1:
            msg = 'Authentication required:'
            dlg = wx.TextEntryDialog(self, msg, 'Authentication',
                                    style=wx.OK|wx.CANCEL|wx.TE_PASSWORD)
            dlg.CentreOnParent()
            if dlg.ShowModal() == wx.ID_OK:
               ident = dlg.GetValue()
               self.nsc_findNS(ident)
            else:
               self.NS = None
               self._log('Connection to Name Server denied!','error')
         else:
            self.NS = None
            self._logError('Unable to connect to Name Server')
      except:
         self.NS = None
         self._logError('Name Server not found!')


   def nsc_list_groups(self, ingroup):
      """
      Returns a list of group names inside given group.
      """
      return self._nsc_list(ingroup, 0)

   def nsc_list_items(self, ingroup):
      """
      Returns a list of item names inside given group.
      """
      return self._nsc_list(ingroup, 1)

   def _nsc_list(self, ingroup, type):
      """
      Generic method for listing either groups or items inside a given group.

      type = 0 : group
      type = 1 : item
      """
      items = []
      if self.NS:
         for name, t in self.NS.list(ingroup):
            if t == type:
               if type == 1:                  
                  uri  = self.NS.resolve('%s.%s' % (ingroup,name))
                  name = '%s (%s)' % (name, uri)
               elif ingroup != ':':
                  name = '%s.%s' % (ingroup, name)
               else:
                  name = '%s%s' % (ingroup, name)
               items.append(name)
      return items

   def nsc_create_group(self, groupName):
      """
      Creating given group
      """
      if self.NS:
         try:
            self.NS.createGroup(groupName)
            self._log('created group (%s)' % (groupName))
            return 1
         except NamingError, e:
            self._logError('unable to create group %s because %s' % (groupName,
                                                                     e))
      return 0

   def nsc_delete_group(self, groupName):
      """
      Deleting given group
      """
      if self.NS:
         try:
            self.NS.deleteGroup(groupName)
            self._log('group %s deleted' % groupName)
            return 1
         except NamingError, e:
            self._logError('unable to delete group %s because %s' % (groupName,
                                                                     e))
      return 0
   
   def nsc_ping(self):
      """
      Ping the current Name Server
      """
      if self.NS:
         try:
            self.NS.ping()
            self._log('ping Name Server (%s): up and running' % self.nsHost)
         except:
            self._logError('Name Server not responding.')
      else:
         self._logError('Name Server not responding')

   def nsc_delete(self, name):
      """Removing given name from the Name Server.
      
      :Parameters:
         - `name`: the name to delete from the Name Server
      """
      try:
         self.NS.unregister(name)
         self._log('%s deleted successfully' % name)
         return 1
      except NamingError, e:
         self._logError('unable to delete %s because %s' % (name, e))
      except:
         self._logError('deletion of %s failed' % name)
      return 0

   def nsc_register_item(self, name, uri):
      """
      Registering new item with given name and uri
      """
      try:
         self.NS.register(name, uri)
         uri = Pyro.core.PyroURI(uri)
         self._log('registered %s with %s' % (name, uri))
         return 1
      except NamingError, e:
         self._logError('unable to register,\nName Server error: %s' % e)
      except Exception, e:
         self._logError('unable to register, error: %s' % e)
      return 0

   def nsc_set_meta(self, name, meta):
      """
      Set user meta data 
      """
      try:
         self.NS.setMeta(name, meta)
         self._log('set user meta data on '+name)
         return 1
      except NamingError, e:
         self._logError('unable to set user meta data,\nName Server error: %s' % e)
      except Exception, e:
         self._logError('unable to set user meta data, error: %s' % e)
      return 0

   def nsc_show_meta(self, name):
      fullName = self.NS.fullName(name)
      try:
         self._log('"%s" system meta info: %s' % (fullName,
                                             self.NS._getSystemMeta(fullName)))
         self._log('"%s" user meta info: %s' % (fullName,
                                                self.NS.getMeta(name)))
      except NamingError, e:
         self._logError('unable to get meta info,\nName Server error: %s' % e)
      except Exception, e:
         self._logError('unable to get meta info, error: %s' % e)
                        
   #-- gui event methods --#
   def OnCheckNS(self, event):      
      if self._checkNS():
         self.update()

   def OnClose(self, event):
      sys.stdout = sys.__stdout__ #restoring the stdout
      self.Destroy()

   def OnCreateGroup(self, event):
      """
      Creating group in selected parent
      """
      tree = self.treeCtrlItems
      items = tree.GetSelections()
      if items:
         if tree.GetPyData(items[0]) == 0:
            # use the selected group
            parentGroupI = items[0]
            parentGroupName = tree.GetItemText(parentGroupI)
         else:
            # take the parent
            parentGroupI = tree.GetItemParent(items[0])
            parentGroupName = tree.GetItemText(parentGroupI)
      else:
         parentGroupI    = tree.GetRootItem()
         parentGroupName = ':'
      msg = 'Create group in "%s", with name:' % parentGroupName
      dlg = wx.TextEntryDialog(self, msg, 'Enter group name')
      dlg.CentreOnParent()
      if dlg.ShowModal() == wx.ID_OK:
         if parentGroupName != ':':
            groupName = '%s.%s' % (parentGroupName, dlg.GetValue())
         else:
            groupName = ':%s' % (dlg.GetValue())
         if self.nsc_create_group(groupName):
            groupI = tree.AppendItem(parentGroupI, groupName)
            tree.SetPyData(groupI, 0)
            tree.SetItemImage(groupI, self.__idGroup)
            tree.SetItemImage(groupI, self.__idGroupOpen,
                              wx.TreeItemIcon_Expanded)
            tree.Expand(parentGroupI)

   def OnSetMeta(self, ev=None):
      """
      set user meta on selected groups + items
      """
      tree = self.treeCtrlItems
      itemsL, groupsL = self._getSelections()
      namesL  = itemsL + groupsL
      if namesL:     
         namesS = ',\n '.join(namesL)
         msg = 'User meta data string for:\n %s' % namesS
         dlg = wx.TextEntryDialog(self, msg, 'Enter meta data')
         dlg.CentreOnParent()
         if dlg.ShowModal() == wx.ID_OK:
            meta=dlg.GetValue()
            for name in namesL:
               self.nsc_set_meta(name,meta)
      
   def OnDelete(self, ev=None):
      """
      Deleting selected items.
      """
      tree = self.treeCtrlItems
      itemsL = tree.GetSelections()
      namesL  = []
      deleteL = []
      for i in itemsL:
         # only items (ie. no groups)
         if tree.GetPyData(i) == 1:
            parent = tree.GetItemParent(i)
            parentName = tree.GetItemText(parent)
            name   = tree.GetItemText(i).split()[0] #only name
            namesL.append('%s.%s' % (parentName, name))
            deleteL.append(i)
      if namesL:     
         namesS = ',\n '.join(namesL)
         ret = show_message_dialog(self,
                         'Really delete following name(s)?:\n %s' % namesS,
                         '-- Confirm --', wx.YES|wx.NO|wx.ICON_QUESTION)
         if ret == wx.ID_YES:
            for name, i in zip(namesL,deleteL):
               if self.nsc_delete(name):
                  tree.Delete(i)
                  
   def OnDeleteGroup(self, ev=None):
      """
      Deleting selected groups.
      """
      tree = self.treeCtrlItems
      itemsL = tree.GetSelections()
      namesL  = []
      deleteL = []
      for i in itemsL:
          # only groups (ie. no items)
          if tree.GetPyData(i) == 0:             
             name   = tree.GetItemText(i)
             if name not in PROTECTED_GROUPS and tree.GetChildrenCount(i)==0:
                namesL.append(name)
                deleteL.append(i)
      if namesL:
         namesS = ',\n'.join(namesL)
         ret = show_message_dialog(self,
                           'Really delete following group(s)?:\n %s' % namesS,
                           '-- Confirm --', wx.YES|wx.NO|wx.ICON_QUESTION)
         if ret == wx.ID_YES:
            for name, i in zip(namesL, deleteL):
               if self.nsc_delete_group(name):
                  tree.Delete(i)
                  
   def OnKeyPressed(self, event):
      """
      Calling delete for both items and groups
      """
      if event.GetKeyCode() == 127:
         # deleting both selected groups and items
         self.OnDelete()
         self.OnDeleteGroup()
      if event.GetKeyCode() == 105: # 105 == 'i'
         # showing meta information on selected item
         self.OnShowMeta()
      event.Skip()
      
   def OnPing(self, event):
      if self._checkNS():
         self.update()
      self.nsc_ping()

      
   def OnRegisterItem(self, event):
      """
      Registering item in selected parent.
      """
      tree = self.treeCtrlItems
      items = tree.GetSelections()
      if items:
         if tree.GetPyData(items[0]) == 0:
            # use the selected group
            parentGroupI = items[0]
            parentGroupName = tree.GetItemText(parentGroupI)
         else:
            parentGroupI = tree.GetItemParent(items[0])
            parentGroupName = tree.GetItemText(parentGroupI)
      else:
         parentGroupI    = tree.GetRootItem()
         parentGroupName = ':'
         
      msg = 'Register new item in "%s", with:\n <name> <URI>' % parentGroupName
      dlg =  wx.TextEntryDialog(self, msg, 'Register item')
      dlg.CentreOnParent()
      if dlg.ShowModal() == wx.ID_OK:
         try:
            itemName, uri = dlg.GetValue().split()
         except:
            self._log('Invalid arguments, use <name> <URI>', 'error')
         else:
            if parentGroupName != ':':
               itemName = '%s.%s' % (parentGroupName, itemName)
            else:
               itemName = ':%s' % (itemName)
            if self.nsc_register_item(itemName, uri):
               label = '%s (%s)' % (dlg.GetValue().split()[0], uri)
               itemI = tree.AppendItem(parentGroupI, label)
               tree.SetPyData(itemI, 1)
               tree.SetItemImage(itemI, self.__idItem)
               tree.SetItemImage(itemI, self.__idItem,
                                 wx.TreeItemIcon_Selected)
               tree.Expand(parentGroupI)
               
   def OnUpdate(self, event):
      self._checkNS()
      self.update()

   def OnShowMeta(self, event=None):
      itemsL, groupsL = self._getSelections()
      for name in itemsL + groupsL:
         self.nsc_show_meta(name)
         
               
   #-- protected methods --#
   def _checkNS(self):
      """
      Reads the new values from the txtCtrlNSHost and txtCtrlNSPort.
      If changed, it tries to connect to the new Name Server.
      """
      changed = 0
      if self.txtCtrlNSHost.IsModified():
         self.nsHost = self.txtCtrlNSHost.GetValue()
         changed = 1
      if self.txtCtrlNSPort.IsModified():
         try:
            port = int(self.txtCtrlNSPort.GetValue())
            self.nsPort = port
         except ValueError:
            self._logError('Integer required for port')
         changed = 1
      if changed:
         self.nsc_findNS()
      return changed

   def _log(self, line, status='info'):
      """Writing given line to the log-textCtrl.
      
      :Parameters:
         - `line`: text to log
         - `status`: status should be 'info' or 'error'. If 'info' the
                     text will be colored blue, if 'error' the text will
                     be red.
      """
      start = self.txtCtrlLog.GetLastPosition()
      self.txtCtrlLog.AppendText('%s\n' % line)
      color = wx.BLACK
      if status == 'info':
         color = wx.BLUE
      elif status == 'error':
         color = wx.RED
      self.txtCtrlLog.SetStyle(start, self.txtCtrlLog.GetLastPosition(),
                               wx.TextAttr(color))

   def _logError(self, line):
      """
      Getting the traceback of previous error, and logging this.
      """
      a, b, tb = sys.exc_info()
      if a == ConnectionClosedError:
         self.NS = None
         self._log('Connection with Name Server lost', 'error')
         self.enable(False)  
      buf = cStringIO.StringIO()
      traceback.print_exc(file = buf)
      self._log('%s:\n%s' % (line, buf.getvalue()), 'error')

   def _setNSData(self):
      """
      Updates the display of current Name Server information.
      """
      try:
         ns_name, t, ns_ip = socket.gethostbyaddr(self.nsHost)
         ns_ip = ns_ip[0]
      except:
         ns_name, ns_ip = self.nsHost, ''
      self.txtCtrlNSHost.SetValue('%s' % ns_name)
      self.txtCtrlNSPort.SetValue('%s' % self.nsPort)
      self.SetTitle('Pyro Name Server ( %s - %s )' % (ns_name, ns_ip))

   def _getSelections(self):
      tree = self.treeCtrlItems
      selectionsL = tree.GetSelections()
      itemsL  = []
      groupsL = []
      for i in selectionsL:
          if tree.GetPyData(i) == 0:
             # group
             groupsL.append(tree.GetItemText(i))
          elif tree.GetPyData(i) == 1:
             # item
             parentName = tree.GetItemText(tree.GetItemParent(i))
             name = tree.GetItemText(i).split()[0]
             itemsL.append('%s.%s' % (parentName, name))
      return itemsL, groupsL
      
   #-- build / bind methods --#
   def _bindEvents(self):
      """
      Binding events to the gui widgets.
      """
      wx.EVT_BUTTON(self, self.buttonPing.GetId(), self.OnPing)
      wx.EVT_BUTTON(self, self.buttonUpdate.GetId(), self.OnUpdate)
      wx.EVT_BUTTON(self, self.buttonClose.GetId(), self.OnClose)
      wx.EVT_BUTTON(self, self.buttonDeleteGroup.GetId(), self.OnDeleteGroup)
      wx.EVT_BUTTON(self, self.buttonCreateGroup.GetId(), self.OnCreateGroup)
      wx.EVT_BUTTON(self, self.buttonDeleteSelected.GetId(), self.OnDelete)
      wx.EVT_BUTTON(self, self.buttonRegisterItem.GetId(), self.OnRegisterItem)
      wx.EVT_BUTTON(self, self.buttonShowMeta.GetId(), self.OnShowMeta)
      wx.EVT_BUTTON(self, self.buttonSetMeta.GetId(), self.OnSetMeta)
      wx.EVT_TEXT_ENTER(self, self.txtCtrlNSHost.GetId(), self.OnCheckNS)
      wx.EVT_TEXT_ENTER(self, self.txtCtrlNSPort.GetId(), self.OnCheckNS)
      wx.EVT_CHAR(self.treeCtrlItems, self.OnKeyPressed)
      
   def _build(self):
      """
      Building widgets and setting static widget data.      
      """
      parent = wx.Panel(self, -1)
      sizer0 = wx.BoxSizer(wx.VERTICAL)
      sizer0.Add(self._buildTopBar(parent), 0, wx.ALIGN_LEFT|wx.GROW, 5)

      splitter = wx.SplitterWindow(parent, -1)
      #- TOP PART --------------------------------------------------------#
      topParent = wx.Panel(splitter, -1)
      topSizer = wx.BoxSizer(wx.VERTICAL)
      self.treeCtrlItems = wx.TreeCtrl(topParent, -1,
                         style = wx.TR_TWIST_BUTTONS|wx.TR_LINES_AT_ROOT|wx.TR_HAS_BUTTONS|wx.TR_HIDE_ROOT|wx.TR_MULTIPLE)
      topSizer.Add(self.treeCtrlItems, 1, wx.EXPAND, 5)
      topParent.SetAutoLayout( True )
      topParent.SetSizer(topSizer )
      topSizer.Fit(topParent)
      topSizer.SetSizeHints(topParent)
      #-------------------------------------------------------------------#
      #- BOTTOM PART -----------------------------------------------------#
      bottomParent = wx.Panel(splitter,-1)
      bottomSizer = wx.BoxSizer(wx.VERTICAL)
      self.txtCtrlLog=wx_StdoutLog(bottomParent, -1, "",
                                  size= wx.Size(-1, 10),
                                  style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_RICH)
      bottomSizer.Add(self.txtCtrlLog, 1, wx.EXPAND, 5)
      bottomParent.SetAutoLayout( True )
      bottomParent.SetSizer(bottomSizer )
      bottomSizer.Fit(bottomParent)
      bottomSizer.SetSizeHints(bottomParent)
      #-------------------------------------------------------------------#
      splitter.SplitHorizontally(topParent,bottomParent, -100)
      sizer0.Add(splitter, 1, wx.EXPAND|wx.ALIGN_CENTRE, 5)
      
      self.buttonClose = wx.Button(parent, -1, 'Close')         # buttonClose
      sizer0.Add(self.buttonClose, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
      
      parent.SetAutoLayout( True )
      parent.SetSizer( sizer0 )
      sizer0.Fit( parent)
      sizer0.SetSizeHints( parent)

   def _buildTopBar(self, parent):
      """
      Widget building
      """
      sizer0 = wx.BoxSizer(wx.VERTICAL)
      #--
      sizer1 = wx.BoxSizer(wx.HORIZONTAL)
      txt1 = wx.StaticText(parent, -1, 'Name Server:')
      txt1.SetForegroundColour(wx.BLUE)
      sizer1.Add(txt1, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTRE|wx.ALL, 5)
      self.txtCtrlNSHost = wx.TextCtrl(parent, -1, '', size=wx.Size(300,-1),
                                      style=wx.TE_PROCESS_ENTER)
      sizer1.Add(self.txtCtrlNSHost, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.TOP|wx.BOTTOM, 5)
      txtColon = wx.StaticText(parent, -1, ':')
      txtColon.SetForegroundColour(wx.BLUE)
      sizer1.Add(txtColon, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTRE|wx.TOP|wx.BOTTOM, 5)
      self.txtCtrlNSPort = wx.TextCtrl(parent, -1, '', size=wx.Size(50,-1),
                                      style=wx.TE_PROCESS_ENTER)
      sizer1.Add(self.txtCtrlNSPort, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.TOP|wx.BOTTOM, 5)
      self.buttonUpdate = wx.Button(parent, -1, 'Update')       # buttonUpdate
      sizer1.Add(self.buttonUpdate, 0, wx.ALIGN_LEFT|wx.ALL, 5)
      self.buttonPing = wx.Button(parent, -1, 'Ping')           # buttonPing
      sizer1.Add(self.buttonPing, 0, wx.ALIGN_LEFT|wx.ALL, 5)
      sizer0.Add(sizer1, 0, wx.ALIGN_LEFT|wx.GROW, 5)
      #--
      lineH1 = wx.StaticLine(parent, -1, style=wx.LI_HORIZONTAL)
      sizer0.Add(lineH1, 0, wx.GROW|wx.ALIGN_CENTRE|wx.LEFT|wx.RIGHT, 5)
      #--
      sizer2 = wx.BoxSizer(wx.HORIZONTAL)
      self.buttonDeleteGroup = wx.Button(parent, -1, ' Delete group(s) ')
      sizer2.Add(self.buttonDeleteGroup, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.TOP|wx.LEFT|wx.BOTTOM, 5)
      self.buttonCreateGroup = wx.Button(parent, -1, ' Create group... ')
      sizer2.Add(self.buttonCreateGroup, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.TOP|wx.LEFT|wx.BOTTOM, 5)
      lineV1 = wx.StaticLine(parent, -1, style=wx.LI_VERTICAL)
      sizer2.Add(lineV1, 0,
                       wx.ALL|wx.GROW, 5)
      self.buttonDeleteSelected = wx.Button(parent, -1,
                                           ' Delete item(s) ')
      sizer2.Add(self.buttonDeleteSelected, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.ALL, 5)
      self.buttonRegisterItem = wx.Button(parent, -1, ' Register item... ')
      sizer2.Add(self.buttonRegisterItem, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 5)
      lineV2 = wx.StaticLine(parent, -1, style=wx.LI_VERTICAL)
      sizer2.Add(lineV2, 0,
                       wx.ALL|wx.GROW, 5)
      self.buttonShowMeta = wx.Button(parent, -1, ' Show meta ')
      sizer2.Add(self.buttonShowMeta, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 5)
      self.buttonSetMeta = wx.Button(parent, -1, ' Set meta ')
      sizer2.Add(self.buttonSetMeta, 0,
                       wx.ALIGN_LEFT|wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 5)
      sizer0.Add(sizer2, 0, wx.ALIGN_LEFT, 5)
      #--
      return sizer0

#----------------------------------------------------------------------#
class WinMessageDialog(wx.Dialog):
    '''
    :Purpose: Message dialog for MS Win.
              The parameters are the same as for wx.MessageDialog

    :Detail: On Windows the native wx.MessageDialog can not
             be centered on top of the parent or positioned, ie.
             it will always be centered on the screen.
             
    '''
    def __init__(self, parent=None, message='Message:',
                 caption='Message', style=wx.OK|wx.CANCEL,pos=wx.DefaultPosition):
        wx.Dialog.__init__(self, parent, -1, caption, size=wx.DefaultSize,
                          style=wx.CAPTION, pos=pos)
        self._build(message, style)
        self.Fit()
        
    def OnButton(self, ev):
        self.EndModal(ev.GetId())
        
    def _build(self, msg, style):
        parent   = wx.Panel(self, -1)
        sizer    = wx.BoxSizer(wx.VERTICAL)
        #-- icon and message --#
        msgSizer = wx.BoxSizer(wx.HORIZONTAL)

        # icon #
        artID = None
        if style & wx.ICON_EXCLAMATION == wx.ICON_EXCLAMATION \
               or style & wx.ICON_HAND == wx.ICON_HAND:
            artID = wx.ART_WARNING
        elif style & wx.ICON_ERROR == wx.ICON_ERROR:
            artID = wx.ART_ERROR
        elif style & wx.ICON_QUESTION == wx.ICON_QUESTION:
            artID = wx.ART_QUESTION
        elif style & wx.ICON_INFORMATION == wx.ICON_INFORMATION:
            artID = wx.ART_INFORMATION
        if artID:
            bmp = wx.ArtProvider_GetBitmap(artID, wx.ART_MESSAGE_BOX, (48,48))
            bmpIcon = wx.StaticBitmap(parent, -1, bmp)
            msgSizer.Add(bmpIcon, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        # msg #
        txtMsg = wx.StaticText(parent, -1, msg, style=wx.ALIGN_CENTRE)
        msgSizer.Add(txtMsg, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(msgSizer, 0, wx.ALIGN_CENTRE, 5)
        line = wx.StaticLine(parent, -1, style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW|wx.ALL, 5)
        #-- buttons --#
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)

        if style & wx.YES_NO == wx.YES_NO:
            btnYes = wx.Button(parent, wx.ID_YES, 'Yes')
            btnSizer.Add(btnYes, 0,
                               wx.ALIGN_CENTRE|wx.LEFT|wx.RIGHT, 10)
            btnNo  = wx.Button(parent, wx.ID_NO, 'No')
            btnSizer.Add(btnNo, 0,
                               wx.ALIGN_CENTRE|wx.LEFT|wx.RIGHT, 10)
            if style & wx.YES_DEFAULT == wx.YES_DEFAULT:
                btnYes.SetDefault()
            elif style & wx.NO_DEFAULT == wx.NO_DEFAULT:
                btnNo.SetDefault()
            wx.EVT_BUTTON(self, wx.ID_YES, self.OnButton)
            wx.EVT_BUTTON(self, wx.ID_NO, self.OnButton)
        else:
            if style & wx.OK == wx.OK:
                btnOK = wx.Button(parent, wx.ID_OK, 'OK')
                btnOK.SetDefault()
                btnSizer.Add(btnOK, 0,
                                   wx.ALIGN_CENTRE|wx.LEFT|wx.RIGHT, 10)
            if style & wx.CANCEL == wx.CANCEL:
                btnCancel = wx.Button(parent, wx.ID_CANCEL, 'Cancel')
                btnSizer.Add(btnCancel, 0,
                                   wx.ALIGN_CENTRE|wx.LEFT|wx.RIGHT, 10)

        sizer.Add(btnSizer, 0, wx.ALIGN_CENTRE|wx.TOP, 5)
        #--
        parent.SetAutoLayout( True )
        parent.SetSizer(sizer )
        sizer.Fit( parent )
        sizer.SetSizeHints( parent )
      
#----------------------------------------------------------------------#
def main(argv):
   """
   The default host will be None if the environment variable
   PYRO_NS_HOSTNAME is not set.
   The default port will be 9090 (Pyro.config.PYRO_NS_PORT) if
   PYRO_NS_BC_PORT environment variable is not set.
   """
   nsHost = os.getenv('PYRO_NS_HOSTNAME')
   nsPort = os.getenv('PYRO_NS_BC_PORT') or Pyro.config.PYRO_NS_PORT
   bcAddr = Pyro.config.PYRO_NS_BC_ADDR
   if bcAddr:
      bcAddr=bcAddr.strip()
   bcAddr=bcAddr or None
      
   class wx_NSCApp(wx.App):
      def OnInit(self):
         Pyro.core.initClient()
         frame = wx_NSC(nsHost, nsPort, bcAddr)
         frame.SetSize(wx.Size(630,500))
         frame.Show(True)
         return True

   app = wx_NSCApp(0)
   app.MainLoop()

# allow easy usage with python -m
if __name__=="__main__":
   main(sys.argv)
