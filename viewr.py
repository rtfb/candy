#!/usr/bin/env python
#
#   Copyright (C) 2008 Vytautas Saltenis.
#
# This file is part of Candy.
#
# Candy is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Candy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Candy. If not, see <http://www.gnu.org/licenses/>.
#

import wx
import wx.stc as stc

faceCourier = 'Courier'
pb = 12

class BuiltinViewerControl (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        styleSpec = 'size:%d,face:%s' % (pb, faceCourier))
        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, styleSpec)
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

