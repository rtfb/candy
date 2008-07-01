#!/usr/bin/env python

import wx
import wx.stc as stc

faceCourier = 'Courier'
pb = 12

class BuiltinViewerControl (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, "size:%d,face:%s" % (pb, faceCourier))
        self.SetFocus ()

    def OnDestroy (self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush ()
        evt.Skip ()

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        key = ''

        if keyCode < 256:
            key = chr (keyCode)

        if key == 'Q':
            self.GetParent ().OnCloseWindow (evt)
        elif key == '/':
            self.searchMode = True
            self.searchStr = ''

class BuiltinViewerFrame (wx.Frame):
    def __init__ (self, parent, ID, title, file, pos = wx.DefaultPosition,
                  size = wx.DefaultSize, style = wx.DEFAULT_FRAME_STYLE):
        wx.Frame.__init__ (self, parent, ID, title, pos, size, style)
        panel = wx.Panel (self, -1)

        self.file = file

        viewr = BuiltinViewerControl (self, -1)
        box = wx.BoxSizer (wx.VERTICAL)
        box.Add (viewr, 1, wx.ALL | wx.GROW, 1)
        self.SetSizer (box)
        self.SetAutoLayout (True)

        viewr.SetText (open (file).read ())
        viewr.SetReadOnly (True)

        self.Bind (wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Maximize ()

    def OnCloseWindow (self, event):
        self.Destroy ()

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        key = ''

        if keyCode < 256:
            key = chr (keyCode)

        if key == 'Q':
            self.OnCloseWindow (evt)

if __name__ == '__main__':
    print 'not a program :-)'

