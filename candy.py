#!/usr/bin/python

# Candy: Commanders Are Not Dead Yet
# Based on File Hunter from http://wiki.wxpython.org/AnotherTutorial

import wx
import os
import time

ID_BUTTON = 100
ID_EXIT = 200
ID_SPLITTER = 300
ID_PANEL = 400

class MyListCtrl (wx.ListCtrl):
    def __init__ (self, parent, id):
        wx.ListCtrl.__init__ (self, parent, id, style = wx.LC_REPORT)
        # LC_LIST

        #self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_LIST_ITEM_ACTIVATED, self.OnListItemActivated)

        images = ['images/empty.png',
                  'images/folder.png',
                  'images/source_py.png',
                  'images/image.png',
                  'images/pdf.png',
                  'images/up16.png']

        self.InsertColumn (0, 'Name')
        self.InsertColumn (1, 'Ext')
        self.InsertColumn (2, 'Size', wx.LIST_FORMAT_RIGHT)
        self.InsertColumn (3, 'Modified')

        self.SetColumnWidth (0, 220)
        self.SetColumnWidth (1, 70)
        self.SetColumnWidth (2, 100)
        self.SetColumnWidth (3, 420)

        #self.il = wx.ImageList (16, 16)
        #for i in images:
        #    self.il.Add (wx.Bitmap (i))
        #self.SetImageList (self.il, wx.IMAGE_LIST_SMALL)

        self.fillList ('.')
        self.selectNeededItem ('', False)
        self.SetFocus ()

    def fillList (self, cwd):
        j = 1
        itemIndex = self.InsertStringItem (0, '..')
        #self.SetItemImage (0, 5)

        files = os.listdir (cwd)
        for i in files:
            if i[0] == '.':
                continue

            (name, ext) = os.path.splitext (i)
            ex = ext[1:]
            size = os.path.getsize (i)
            sec = os.path.getmtime (i)
            self.InsertStringItem (j, name)
            self.SetStringItem (j, 1, ex)
            self.SetStringItem (j, 2, str (size) + ' B')
            self.SetStringItem (j, 3, time.strftime ('%Y-%m-%d %H:%M', time.localtime (sec)))

            if os.path.isdir (i):
                self.SetItemTextColour (j, wx.BLUE)
                boldFont = wx.Font (10, wx.NORMAL, wx.NORMAL, wx.BOLD)
                self.SetItemFont (j, boldFont)

            """
            if os.path.isdir (i):
                self.SetItemImage (j, 1)
            elif ex == 'py':
                self.SetItemImage (j, 2)
            elif ex == 'jpg':
                self.SetItemImage (j, 3)
            elif ex == 'pdf':
                self.SetItemImage (j, 4)
            else:
                self.SetItemImage (j, 0)
                """

            #if (j % 2) == 0:
            #    self.SetItemBackgroundColour (j, '#e6f1f5')
            j = j + 1

    def selectNeededItem (self, oldDir, upwards):
        if upwards:
            item = self.FindItem (0, oldDir)

            if item != -1:
                self.Select (item)
                self.Focus (item)
        else:
            self.Select (0)
            self.Focus (0)

    def OnListItemActivated (self, listEvent):
        text = listEvent.GetText ()

        if os.path.isdir (text):
            oldDir = os.path.split (os.getcwd ())[1]
            os.chdir (text)
            self.DeleteAllItems ()
            self.fillList (os.getcwd ())
            self.selectNeededItem (oldDir, text == '..')

    def OnKeyDown (self, event):
        print "OKD in MyListCtrl"
        keycode = event.GetKeyCode ()
        self.GetParent ().GetParent ().sb.SetStatusText (str (keycode))

        if keycode == wx.WXK_RETURN:
            doEnterKey ()

        if keycode == wx.WXK_ESCAPE:
            ret  = wx.MessageBox ('Are you sure to quit?',
                                  'Question',
                                  wx.YES_NO | wx.CENTRE | wx.NO_DEFAULT,
                                  self)
            if ret == wx.YES:
                self.Close ()

        event.Skip ()

class MySplitterWindow (wx.SplitterWindow):
    def __init__ (self, parent, id):
        wx.SplitterWindow.__init__ (self, parent, id, style = wx.SP_BORDER)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)

    def OnKeyDown (self, event):
        print "OKD in MySplitterWindow"
        event.Skip ()

class Candy (wx.Frame):
    def __init__ (self, parent, id, title):
        wx.Frame.__init__ (self, parent, -1, title)

        self.splitter = MySplitterWindow (self, ID_SPLITTER)
        self.splitter.SetMinimumPaneSize (50)

        p1 = MyListCtrl (self.splitter, -1)
        p2 = MyListCtrl (self.splitter, -1)
        self.splitter.SplitVertically (p1, p2)

        self.Bind (wx.EVT_SIZE, self.OnSize)
        self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)

        filemenu= wx.Menu ()
        filemenu.Append (ID_EXIT, "E&xit", " Terminate the program")
        editmenu = wx.Menu ()
        netmenu = wx.Menu ()
        showmenu = wx.Menu ()
        configmenu = wx.Menu ()
        helpmenu = wx.Menu ()

        menuBar = wx.MenuBar ()
        menuBar.Append (filemenu, "&File")
        menuBar.Append (editmenu, "&Edit")
        menuBar.Append (netmenu, "&Net")
        menuBar.Append (showmenu, "&Show")
        menuBar.Append (configmenu, "&Config")
        menuBar.Append (helpmenu, "&Help")
        self.SetMenuBar (menuBar)
        self.Bind (wx.EVT_MENU, self.OnExit, id = ID_EXIT)

        """
        tb = self.CreateToolBar (wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_TEXT)
        tb.AddSimpleTool (10, wx.Bitmap ('images/previous.png'), 'Previous')
        tb.AddSimpleTool (20, wx.Bitmap ('images/up.png'), 'Up one directory')
        tb.AddSimpleTool (30, wx.Bitmap ('images/home.png'), 'Home')
        tb.AddSimpleTool (40, wx.Bitmap ('images/refresh.png'), 'Refresh')
        tb.AddSeparator ()
        tb.AddSimpleTool (50, wx.Bitmap ('images/write.png'), 'Editor')
        tb.AddSimpleTool (60, wx.Bitmap ('images/terminal.png'), 'Terminal')
        tb.AddSeparator ()
        tb.AddSimpleTool (70, wx.Bitmap ('images/help.png'), 'Help')
        tb.Realize ()
        """

        self.sizer2 = wx.BoxSizer (wx.HORIZONTAL)

        button1 = wx.Button (self, ID_BUTTON + 1, "F3 View")
        button2 = wx.Button (self, ID_BUTTON + 2, "F4 Edit")
        button3 = wx.Button (self, ID_BUTTON + 3, "F5 Copy")
        button4 = wx.Button (self, ID_BUTTON + 4, "F6 Move")
        button5 = wx.Button (self, ID_BUTTON + 5, "F7 Mkdir")
        button6 = wx.Button (self, ID_BUTTON + 6, "F8 Delete")
        button7 = wx.Button (self, ID_BUTTON + 7, "F9 Rename")
        button8 = wx.Button (self, ID_EXIT, "F10 Quit")

        self.sizer2.Add (button1, 1, wx.EXPAND)
        self.sizer2.Add (button2, 1, wx.EXPAND)
        self.sizer2.Add (button3, 1, wx.EXPAND)
        self.sizer2.Add (button4, 1, wx.EXPAND)
        self.sizer2.Add (button5, 1, wx.EXPAND)
        self.sizer2.Add (button6, 1, wx.EXPAND)
        self.sizer2.Add (button7, 1, wx.EXPAND)
        self.sizer2.Add (button8, 1, wx.EXPAND)

        self.Bind (wx.EVT_BUTTON, self.OnExit, id = ID_EXIT)

        self.sizer = wx.BoxSizer (wx.VERTICAL)
        self.sizer.Add (self.splitter, 1, wx.EXPAND)
        self.sizer.Add (self.sizer2, 0, wx.EXPAND)
        self.SetSizer (self.sizer)

        size = wx.DisplaySize ()
        self.SetSize (size)

        self.sb = self.CreateStatusBar ()
        self.sb.SetStatusText (os.getcwd ())
        self.Center ()
        self.Show (True)

    def OnExit (self, e):
        self.Close (True)

    def OnSize (self, event):
        size = self.GetSize ()
        self.splitter.SetSashPosition (size.x / 2)
        self.sb.SetStatusText (os.getcwd ())
        event.Skip ()

    def OnDoubleClick (self, event):
        size =  self.GetSize ()
        self.splitter.SetSashPosition (size.x / 2)

    def OnKeyDown (self, event):
        print "OKD in Candy"
        keycode = event.GetKeyCode ()
        self.sb.SetStatusText (str (keycode))
        if keycode == wx.WXK_ESCAPE:
            ret  = wx.MessageBox ('Are you sure to quit?',
                                  'Question',
                                  wx.YES_NO | wx.CENTRE | wx.NO_DEFAULT,
                                  self)
            if ret == wx.YES:
                self.Close ()
        event.Skip ()

def main ():
    app = wx.App (0)
    candy = Candy (None, -1, 'File Hunter')
    app.MainLoop ()

if __name__ == '__main__':
    main ()

