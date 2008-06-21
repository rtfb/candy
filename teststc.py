#!/usr/bin/python

import wx
import wx.stc as stc
import os
import time
import sys

numTotalColumns = 5

class MySTC (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        #self.currSelection = (0, 0)     # Top left item in the list
        self.linesPerCol = 0
        self.charsPerCol = 0
        self.numFullColumns = 0
        self.items = []
        self.selectedItem = 0

    def setCharsPerCol (self, chars):
        self.charsPerCol = chars

    def setLinesPerCol (self, lines):
        self.linesPerCol = lines

    def setItemList (self, list):
        self.items = list
        self.numFullColumns = len (self.items) / self.linesPerCol

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

        if key == 'J':
            self.moveSelectionDown ()
        elif key == 'K':
            self.moveSelectionUp ()
        elif key == 'H':
            self.moveSelectionLeft ()
        elif key == 'L':
            self.moveSelectionRight ()

        self.setSelection ()

    def moveSelectionDown (self):
        self.selectedItem += 1

        if self.selectedItem >= len (self.items):
            self.selectedItem = 0

    def moveSelectionUp (self):
        self.selectedItem -= 1

        if self.selectedItem < 0:
            self.selectedItem = len (self.items) - 1

    def moveSelectionLeft (self):
        self.selectedItem -= self.linesPerCol

        if self.selectedItem < 0:
            self.selectedItem += self.linesPerCol   # undo the decrement and start calculating from scratch
            numFullLines = len (self.items) % self.linesPerCol
            bottomRightIndex = self.linesPerCol * (self.numFullColumns + 1) - 1

            if self.selectedItem % self.linesPerCol > numFullLines:
                bottomRightIndex = self.linesPerCol * self.numFullColumns - 1

            self.selectedItem = self.selectedItem - self.linesPerCol + bottomRightIndex

    def moveSelectionRight (self):
        self.selectedItem += self.linesPerCol

        if self.selectedItem > len (self.items):
            self.selectedItem -= self.linesPerCol
            self.selectedItem = self.selectedItem % self.linesPerCol + 1

    def setSelection (self):
        itemX = self.selectedItem / self.linesPerCol
        itemY = self.selectedItem % self.linesPerCol
        numNonEmptyColumns = self.numFullColumns + 1
        numFullLines = len (self.items) % self.linesPerCol

        if itemY > numFullLines:
            selStart = numFullLines * numNonEmptyColumns * self.charsPerCol \
                       + (itemY - numFullLines) * self.numFullColumns * self.charsPerCol \
                       + (itemX * self.charsPerCol) + itemY
        else:
            selStart = itemY * numNonEmptyColumns * self.charsPerCol + (itemX * self.charsPerCol) + itemY

        self.SetSelection (selStart, selStart + self.charsPerCol)

    def OnModified (self, evt):
        pass
        #print evt.GetLinesAdded ()
        #print evt.GetText ()
        #self.log.write ("""OnModified
        #Mod type:     %s
        #At position:  %d
        #Lines added:  %d
        #Text Length:  %d
        #Text:         %s\n""" % (self.transModType (evt.GetModificationType ()),
        #                         evt.GetPosition (),
        #                         evt.GetLinesAdded (),
        #                         evt.GetLength (),
        #                         repr(evt.GetText ())))

    def transModType (self, modType):
        st = ""
        table = [(stc.STC_MOD_INSERTTEXT, "InsertText"),
                 (stc.STC_MOD_DELETETEXT, "DeleteText"),
                 (stc.STC_MOD_CHANGESTYLE, "ChangeStyle"),
                 (stc.STC_MOD_CHANGEFOLD, "ChangeFold"),
                 (stc.STC_PERFORMED_USER, "UserFlag"),
                 (stc.STC_PERFORMED_UNDO, "Undo"),
                 (stc.STC_PERFORMED_REDO, "Redo"),
                 (stc.STC_LASTSTEPINUNDOREDO, "Last-Undo/Redo"),
                 (stc.STC_MOD_CHANGEMARKER, "ChangeMarker"),
                 (stc.STC_MOD_BEFOREINSERT, "B4-Insert"),
                 (stc.STC_MOD_BEFOREDELETE, "B4-Delete")
                 ]

        for flag, text in table:
            if flag & modType:
                st = st + text + " "

        if not st:
            st = 'UNKNOWN'

        return st

#face1 = 'Helvetica'
#face2 = 'Times'
faceCourier = 'Courier'
pb = 12

def lJustAndCut (text, width):
    newText = text.ljust (width)

    if len (newText) > width:
        newText = newText [:width]

    return newText

class Candy (wx.Frame):
    def __init__ (self, parent, id, title):
        wx.Frame.__init__ (self, parent, -1, title)

        self.p1 = MySTC (self, -1)

        # make some styles
        self.p1.StyleSetSpec (stc.STC_STYLE_DEFAULT, "size:%d,face:%s" % (pb, faceCourier))
        """
        self.p1.StyleClearAll ()
        self.p1.StyleSetSpec (1, "size:%d,bold,face:%s,fore:#0000FF" % (pb + 2, face3))
        self.p1.StyleSetSpec (2, "face:%s,italic,fore:#FF0000,size:%d" % (face3, pb))
        self.p1.StyleSetSpec (3, "face:%s,bold,size:%d" % (face3, pb + 2))
        self.p1.StyleSetSpec (4, "face:%s,size:%d" % (face3, pb - 1))

        # Now set some text to those styles...  Normally this would be
        # done in an event handler that happens when text needs displayed.
        self.p1.StartStyling (98, 0xff)
        self.p1.SetStyling (6, 1)  # set style for 6 characters using style 1

        self.p1.StartStyling (190, 0xff)
        self.p1.SetStyling (20, 2)

        self.p1.StartStyling (310, 0xff)
        self.p1.SetStyling (4, 3)
        self.p1.SetStyling (2, 0)
        self.p1.SetStyling (10, 4)
        """

        self.Bind (wx.EVT_SIZE, self.OnSize)
        #self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)

        size = wx.DisplaySize ()
        self.SetSize (size)

        self.sb = self.CreateStatusBar ()
        self.sb.SetStatusText (os.getcwd ())
        self.Center ()
        self.Show (True)

        #height = self.p1.GetRect ()[3]
        #width = self.p1.GetRect ()[2]
        width, height = self.p1.GetClientSizeTuple ()
        colWidth = width / numTotalColumns
        lineHeight = self.p1.TextHeight (0)
        linesPerCol = height / lineHeight
        charWidth = self.p1.TextWidth (stc.STC_STYLE_DEFAULT, 'a')
        charsPerCol = width / charWidth / numTotalColumns

        files = os.listdir ('/home/rtfb')
        linesToAdd = ['' for i in range (linesPerCol)]

        currLine = 0
        for file in files:
            linesToAdd[currLine] += lJustAndCut (file, charsPerCol)
            currLine += 1

            if currLine > linesPerCol - 1:
                currLine = 0

        print linesPerCol, len (linesToAdd)
        self.p1.SetText ('\n'.join (linesToAdd))
        self.p1.setCharsPerCol (charsPerCol)
        self.p1.setLinesPerCol (linesPerCol)
        self.p1.setItemList (files)
        self.p1.EmptyUndoBuffer ()
        self.p1.SetReadOnly (True)
        self.p1.SetFocus ()
        self.p1.SetViewWhiteSpace (stc.STC_WS_VISIBLEALWAYS)
        self.p1.SetViewEOL (True)
        self.p1.SetSelBackground (1, "yellow")

    def OnExit (self, e):
        self.Close (True)

    def OnSize (self, event):
        size = self.GetSize ()
        event.Skip ()

    def OnDoubleClick (self, event):
        size =  self.GetSize ()

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
    candy = Candy (None, -1, 'Candy')
    app.MainLoop ()

if __name__ == '__main__':
    main ()

