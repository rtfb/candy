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

# If text interface will ever be needed, this one might be handy:
# http://freshmeat.net/projects/python-urwid/

import os
import time
import sys
import pdb
import platform
import subprocess

import wx
import wx.stc as stc
import wx.lib.pubsub as pubsub

if platform.system() == 'Windows':
    try:
        import win32api
    except ImportError:
        print 'You seem to be running Windows and don\'t have win32api.'
        print 'Tisk tisk tisk...'

import keyboard
import util
from status_line import StatusLine
import data
from constants import *


project_dir = os.path.dirname(__file__)
general_conf_path = os.path.join(project_dir, u'general.conf')
general_config = util.read_config(general_conf_path)
color_conf = os.path.join(project_dir, u'colorscheme-default.conf')
color_scheme = util.read_config(color_conf)


class VisualItem(object):
    """
    An item to hold visual representation. E.g. if the external item is a
    filename, this one will hold things like justified name, startChar in
    the ViewWindow coords and the like. Number of these objects is the number
    RawItems that actually fit on screen (at least partially).
    """
    def __init__(self):
        # Character on the row-representing string, which is the str[0]-th
        # char of this item's visual representation. Will not be negative,
        # since objects of this class represent only visible things, even
        # if only a part of the thing is visible
        self.start_char_on_line = 0

        # Length of the visible item in characters. Will be as much characters
        # as actually visible
        self.vis_len_in_chars = 0

        # The first byte in the string, representing the line that contains
        # this item. This is needed because of silly implementation detail
        # of STC: it needs to start (and apply) styling according to bytes,
        # not the characters. So for Unicode strings, I have to keep track
        # of bytes, not only characters.
        self.start_byte_on_line = 0

        # Length of the item's visual repr, expressed in bytes (same reasons
        # as with start_byte_on_line).
        self.vis_len_in_bytes = 0

        # Since objects of this class only represent things that are
        # on-screen, there's no need for special check. We only need to
        # record whether the whole item was fit to screen
        self.fully_in_view = False

    def set_start_byte(self, visible_text_line):
        chars_before_this_item = visible_text_line[:self.start_char_on_line]
        self.start_byte_on_line = len(chars_before_this_item.encode('utf-8'))


class SmartJustifier(object):
    def __init__(self, width):
        self.width = width
        self.num_dots = 3

    def justify(self, text):
        if len(text) <= self.width:
            return text.ljust(self.width)

        root, ext = os.path.splitext(text)
        new_width = self.width - self.num_dots

        if ext and ext != u'':
            new_width -= len(ext)

        if new_width <= 5:       # 5 = len('a...b')
            half_width_ceil = 1
            half_width_floor = 1
            ext_top = (self.width - half_width_ceil - half_width_floor -
                       self.num_dots)
        else:
            half_width_ceil = util.int_div_ceil(new_width, 2)
            half_width_floor = util.int_div_floor(new_width, 2)
            ext_top = len(ext)

        if ext_top > len(ext):
            half_width_ceil += ext_top - len(ext)

        dots = u'.' * self.num_dots
        left_part = root[:half_width_ceil]
        right_part = root[-half_width_floor:]
        new_text = left_part + dots + right_part + ext[:ext_top]

        return new_text


# The width/height/left/right are in characters
class ViewWindow(object):
    def __init__(self, width, height):
        # Number of characters that can fit in whole width of the pane
        self.width = width

        # Number of lines per single column
        self.height = height

        # How much characters to the right is the view window
        self.left = 0

        # Number of columns of items across all the width of the pane
        self.num_columns = 0

    def right(self):
        return self.left + self.width

    # only handles horizontal dimension
    def char_in_view(self, char_pos):
        return char_pos >= self.left and char_pos < self.right()


class PanelController(object):
    def __init__(self, parent, modelSignature, controllerSignature):
        self.model = data.PanelModel(modelSignature)
        self.controllerSignature = controllerSignature
        self.view = Panel(parent)
        self.bindEvents()
        signature = modelSignature + 'NEW ITEMS'
        pubsub.Publisher().subscribe(self.afterDirChange, signature)

        self.subscribe(self.searchCtrlEnter, 'CONTROL ENTER')
        self.subscribe(self.searchEnter, 'ENTER')
        self.subscribe(self.searchEscape, 'ESCAPE')
        self.subscribe(self.searchNewStatusLineText, 'NEW STATUS LINE TEXT')

        # String being searched incrementally
        self.searchStr = ''

        # Index of an item that is an accepted search match. Needed to know
        # which next match should be focused upon go-to-next-match
        self.searchMatchIndex = -1

        # Index of an item that is currently selected
        self.selectedItem = 0

        self.keys = keyboard.KeyboardConfig()
        self.keys.load(u'keys.conf', self)

    def subscribe(self, func, signature):
        msg = self.controllerSignature + signature
        pubsub.Publisher().subscribe(func, msg)

    def numItems(self):
        return len(self.model.items)

    # Used in tests
    def clearList(self):
        self.model.set_items([])
        self.selectedItem = 0
        self.view.numFullColumns = 0

    def initializeViewSettings(self, num_columns=3):
        self.view.initializeViewSettings(self.model.items, num_columns)
        self.view.highlightSearchMatches(self.model.items, self.searchStr)
        self.setSelectionOnCurrItem()

    def initializeAndShowInitialView(self):
        self.initializeViewSettings()
        self.goHome()

        # This one is needed here to get the initial focus:
        self.view.SetFocus()

    def bindEvents(self):
        self.view.Bind(wx.EVT_CHAR, self.OnChar)
        self.view.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.view.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)

    def handleKeyEvent(self, keyCode, keyMod):
        func = self.keys.getFunc(keyCode, keyMod)

        if func:
            func()
            self.setSelectionOnCurrItem()

    def displaySelectionInfo(self):
        # in the line below, I'm subtracting 1 from number of items because
        # of '..' pseudoitem
        if self.numItems() > 0:
            item = self.getSelection()
            statusText = u'[Folder view]: %s\t%d item(s) -- \'%s\' in %s' \
                         % (os.getcwdu(), self.numItems() - 1,
                            item.file_name, item.path)
            self.view.getFrame().status_bar.SetStatusText(statusText)

    def OnKeyDown(self, evt):
        keyCode = evt.GetKeyCode()
        keyMod = evt.GetModifiers()
        self.handleKeyEvent(keyCode, keyMod)

    def OnChar(self, evt):
        keyCode = evt.GetKeyCode()
        self.handleKeyEvent(keyCode, None)

    def OnSetFocus(self, evt):
        self.view.onSetFocus()
        os.chdir(self.model.working_dir)

    def quiter(self):
        sys.exit(0)

    def updateView(self):
        self.view.updateDisplayByItems(self.model.items)

    def updir(self):
        self.selectedItem = 0
        self.clearScreen()
        self.selectedItem = self.model.updir()

    def listDriveLetters(self):
        if platform.system() != 'Windows':
            return

        self.selectedItem = 0
        self.model.set_items(data.collect_drive_letters())

    def flattenDirectory(self):
        self.model.flatten_directory()
        self.model.fill_list_by_working_dir(self.model.working_dir)

    def changeDir(self, fullPath, searchStr=u''):
        self.model.set_dir_filter(searchStr)
        os.chdir(fullPath)
        self.clearScreen()
        self.selectedItem = 0
        self.model.fill_list_by_working_dir(fullPath)

    def listSearchMatches(self, searchStr):
        self.changeDir(self.model.working_dir, searchStr)

    def downdir(self, dirName):
        self.changeDir(os.path.join(self.model.working_dir, dirName))

    def goHome(self):
        self.changeDir(os.path.expanduser(u'~'))

    def afterDirChange(self, message):
        self.updateView()
        self.setSelectionOnCurrItem()

    def searchCtrlEnter(self, msg):
        self.view.SetFocus()
        self.listSearchMatches(self.searchStr)

    def searchEnter(self, msg):
        self.view.SetFocus()
        # Here we want to stop searching and set focus on first search match.
        # But if there was no match, we want to behave more like when we cancel
        # search. Except we've no matches to clear, since no match means
        # nothing was highlighted
        if self.searchMatchIndex != -1:
            self.selectedItem = self.searchMatchIndex
            self.setSelectionOnCurrItem()

    def searchEscape(self, msg):
        self.view.SetFocus()
        self.view.applyDefaultStyles(self.model.items)  # clean matches

    def searchNewStatusLineText(self, msg):
        self.searchStr = msg.data
        self.searchMatchIndex = self.incrementalSearch(self.searchStr)

    def onEnter(self):
        selection = self.getSelection()

        if selection.is_dir:
            if selection.file_name == u'..':
                self.updir()
            else:
                self.downdir(selection.file_name)
        else:
            base, ext = os.path.splitext(selection.file_name)
            commandLine = util.resolve_command_by_file_ext(ext[1:].lower())

            if commandLine:
                subprocess.call([commandLine, selection.file_name])

    def clearScreen(self):
        self.view.clearScreen()

    def onNextMatch(self):
        item = self.selectedItem + 1
        self.searchMatchIndex = self.model.next_search_match(self.searchStr,
                                                             item)
        self.selectedItem = self.searchMatchIndex

    def incrementalSearch(self, searchStr):
        matchIndex = self.model.next_search_match(searchStr, self.selectedItem)
        self.view.moveItemIntoView(self.model.items, matchIndex)
        self.view.highlightSearchMatches(self.model.items, searchStr)
        return matchIndex

    def onStartIncSearch(self):
        self.searchStr = ''
        self.view.getFrame().status_line.SetText(u'/')
        self.view.getFrame().status_line.GotoPos(1)
        self.view.getFrame().status_line.SetFocus()

    def setSelectionOnCurrItem(self):
        if self.numItems() <= 0:
            return

        item = self.getSelection()
        if not item.visual_item or not item.visual_item.fully_in_view:
            self.view.moveItemIntoView(self.model.items, self.selectedItem)
            self.view.highlightSearchMatches(self.model.items, self.searchStr)

        self.view.setSelectionOnItem(item)
        self.displaySelectionInfo()

    def moveSelectionDown(self):
        self.selectedItem += 1

        if self.selectedItem >= self.numItems():
            self.selectedItem = 0

    def moveSelectionUp(self):
        self.selectedItem -= 1

        if self.selectedItem < 0:
            self.selectedItem = self.numItems() - 1

        # This can happen if self.model.items is empty
        if self.selectedItem < 0:
            self.selectedItem = 0

    def moveSelectionLeft(self):
        self.selectedItem -= self.view.viewWindow.height

        if self.numItems() == 0:
            self.selectedItem = 0
            return

        if self.selectedItem < 0:
            # undo the decrement and start calculating from scratch:
            self.selectedItem += self.view.viewWindow.height

            # Avoiding too long line here... but...
            # TODO: figure out how to deal with that long line without
            # splitting. It suggests some nasty coupling.
            selItem = self.selectedItem
            numItems = self.numItems()
            selItem = self.view.updateSelectedItemLeft(selItem, numItems)
            self.selectedItem = selItem

        if self.selectedItem == -1:
            self.selectedItem = self.numItems() - 1

    def moveSelectionRight(self):
        self.selectedItem += self.view.viewWindow.height

        if self.numItems() == 0:
            self.selectedItem = 0
            return

        if self.selectedItem > self.numItems():
            self.selectedItem -= self.view.viewWindow.height
            self.selectedItem %= self.view.viewWindow.height
            self.selectedItem += 1

        if self.selectedItem == self.numItems():
            self.selectedItem = 0

    def moveSelectionZero(self):
        self.selectedItem = 0

    def moveSelectionLast(self):
        self.selectedItem = self.numItems() - 1

        if self.selectedItem < 0:
            self.selectedItem = 0

    def startEditor(self):
        subprocess.call([u'gvim', self.getSelection().file_name])

    def refresh(self):
        backup = self.selectedItem
        self.changeDir(self.model.working_dir)
        self.view.highlightSearchMatches(self.model.items, self.searchStr)
        self.selectedItem = backup

    def getSelection(self):
        return self.model.items[self.selectedItem]

    def startViewer(self):
        import viewr
        file = self.getSelection().file_name
        wnd = viewr.BuiltinViewerFrame(self.view, -1, file, file)
        wnd.Show(True)

    def switchPane(self):
        self.view.getFrame().switch_pane()
        self.afterDirChange(None)

    def switchSplittingMode(self):
        self.view.switchSplittingMode()


class Panel(stc.StyledTextCtrl):
    def __init__(self, parent):
        stc.StyledTextCtrl.__init__(self, parent)

        # No margins and scroll bars over here!
        self.SetMarginWidth(1, 0)
        self.SetUseHorizontalScrollBar(0)

        self.bindEvents()
        self.setStyles()

        self.viewWindow = None

        # Number of characters per column width
        self.charsPerCol = 0

        # Number of columns in the whole-wide view, that are filled from top
        # to bottom
        self.numFullColumns = 0

        # A set of VisualItems that are referenced from subset of
        # controller.items and represent visible parts of them on screen.
        self.visualItems = []

        # List of full-width lines, containing the text of the items.
        # Only sublines of these lines are displayed both for performance
        # reasons and to bypass a bug in STC, failing to display extremely
        # long lines correctly.
        self.fullTextLines = []

    def bindEvents(self):
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnLoseFocus)

    def setStyles(self):
        # This repeats the default: the five bits are for styling, the rest
        # three are for indicators (like green squiggle line). I'm setting it
        # explicitly to have a reference to the starting point in the code if I
        # ever need some messing around with indicators.
        self.SetStyleBits(5)

        faceCourier = general_config['font-face'] # 'Courier'
        pb = int(general_config['font-size']) # 12
        sizeAndFace = 'size:%d,face:%s' % (pb, faceCourier)

        # Set the styles according to color scheme
        styleSpec = sizeAndFace + ',back:%s,fore:%s' \
                    % (color_scheme['background'], color_scheme['default-text'])
        self.StyleSetSpec(stc.STC_STYLE_DEFAULT, styleSpec)
        self.StyleClearAll()
        styleSpec = sizeAndFace + ',bold,fore:%s' % (color_scheme['folder'])
        self.StyleSetSpec(STYLE_FOLDER, styleSpec)
        styleSpec = sizeAndFace + ',bold,fore:%s,back:%s' \
                    % (color_scheme['search-highlight-fore'],
                       color_scheme['search-highlight-back'])
        self.StyleSetSpec(STYLE_INC_SEARCH, styleSpec)
        self.SetSelBackground(1, color_scheme['selection-inactive'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def initializeViewSettings(self, items, num_columns):
        width, height = self.GetClientSizeTuple()
        lineHeight = self.TextHeight(0)
        charWidth = self.TextWidth(stc.STC_STYLE_DEFAULT, 'a')

        # Here viewWindow.left will be set to 0. Even if it's not,
        # it will be brought back to life when doing moveItemIntoView:
        self.viewWindow = ViewWindow(width / charWidth,
                                     height / lineHeight)
        self.viewWindow.num_columns = num_columns
        self.charsPerCol = width / charWidth / self.viewWindow.num_columns
        self.clearScreen()
        self.updateDisplayByItems(items)

    def setDebugWhitespace(self):
        if general_config['debug-whitespace'].lower() == 'true':
            self.SetViewWhiteSpace(stc.STC_WS_VISIBLEALWAYS)
            self.SetViewEOL(True)
        else:
            self.SetViewWhiteSpace(stc.STC_WS_INVISIBLE)
            self.SetViewEOL(False)

    def createVisualItem(self, rawItem):
        row = rawItem.coords[1]
        vi = VisualItem()
        start_char_on_line = rawItem.start_char_on_line - self.viewWindow.left
        endCharOnLine = start_char_on_line + len(rawItem.visible_part)
        visibleLine = self.GetLine(row)

        # Partially, to the left of ViewWindow:
        if start_char_on_line < 0 and endCharOnLine >= 0:
            vi.vis_len_in_chars = start_char_on_line + len(rawItem.visible_part)
            vi.start_char_on_line = 0
            vi.set_start_byte(visibleLine)
            tail = rawItem.visible_part[-vi.vis_len_in_chars:]
            vi.vis_len_in_bytes = len(tail.encode('utf-8'))
            vi.fully_in_view = False
            return vi

        # Partially, to the right of ViewWindow:
        if endCharOnLine >= self.viewWindow.width \
           and start_char_on_line < self.viewWindow.width:
            vi.start_char_on_line = start_char_on_line
            vi.vis_len_in_chars = self.viewWindow.width - vi.start_char_on_line
            vi.set_start_byte(visibleLine)
            head = rawItem.visible_part[:vi.vis_len_in_chars]
            vi.vis_len_in_bytes = len(head.encode('utf-8'))
            vi.fully_in_view = False
            return vi

        # Fully in view:
        vi.start_char_on_line = start_char_on_line
        vi.vis_len_in_chars = len(rawItem.visible_part)
        vi.set_start_byte(visibleLine)
        vi.vis_len_in_bytes = len(rawItem.visible_part.encode('utf-8'))
        vi.fully_in_view = True
        return vi

    def extractVisualItems(self, items):
        self.visualItems = []

        for i in items:
            i.visual_item = None
            startCharInView = self.viewWindow.char_in_view(i.start_char_on_line)
            endCharPos = i.start_char_on_line + len(i.visible_part)
            endCharInView = self.viewWindow.char_in_view(endCharPos)

            if startCharInView or endCharInView:
                i.visual_item = self.createVisualItem(i)
                self.visualItems.append(i.visual_item)

    def extractVisibleSubLines(self):
        visibleSublines = []

        for line in self.fullTextLines:
            rawSubLine = line[self.viewWindow.left : self.viewWindow.right()]
            subLine = rawSubLine.ljust(self.viewWindow.width)
            visibleSublines.append(subLine)

        return u'\n'.join(visibleSublines).encode('utf-8')

    def constructFullTextLines(self, items):
        if self.viewWindow.height == 0:
            # Avoid division by zero
            self.viewWindow.height = 1

        self.numFullColumns = len(items) / self.viewWindow.height
        self.fullTextLines = ['' for i in range(self.viewWindow.height)]

        row = 0
        column = 0
        sj = SmartJustifier(self.charsPerCol - 1)

        for item in items:
            visible_part = sj.justify(item.file_name) + u' '
            item.coords =(column, row)
            item.start_char_on_line = len(self.fullTextLines[row])
            utf8Line = self.fullTextLines[row].encode('utf-8')
            item.start_byte_on_line = len(utf8Line)
            item.visible_part = visible_part
            self.fullTextLines[row] += visible_part
            row += 1

            if row > self.viewWindow.height - 1:
                row = 0
                column += 1

    def updateDisplayByItems(self, rawItems, constructFullLines=True):
        self.clearScreen()
        self.SetReadOnly(False)

        if constructFullLines:
            self.constructFullTextLines(rawItems)

        self.SetTextUTF8(self.extractVisibleSubLines())
        self.extractVisualItems(rawItems)
        self.EmptyUndoBuffer()
        self.SetReadOnly(True)
        self.setDebugWhitespace()
        self.applyDefaultStyles(rawItems)

    def getFrame(self):
        return self.GetParent().GetParent()

    def OnDestroy(self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush()
        evt.Skip()

    def clearScreen(self):
        self.SetReadOnly(False)
        self.ClearAll()
        self.SetReadOnly(True)

    def switchSplittingMode(self):
        self.getFrame().switch_splitting_mode()

    def onSetFocus(self):
        self.SetSelBackground(1, color_scheme['selection-back'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def OnLoseFocus(self, evt):
        self.SetSelBackground(1, color_scheme['selection-inactive'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def highlightSearchMatches(self, items, searchStr):
        self.applyDefaultStyles(items)
        searchStrLower = searchStr.lower()

        for i in items:
            if i.visual_item:
                matchOffset = i.file_name.lower().find(searchStrLower)

                if matchOffset != -1:
                    endOfHighlight = i.visual_item.vis_len_in_chars
                    if matchOffset + len(searchStr) > endOfHighlight:
                        # TODO: this is a temporary hack to make the highlight
                        # always fit the visible part of an item. As we must
                        # run the search through the actual filename by
                        # definition, this match offset can be way off the
                        # visible part of an item. This issue of highlighting a
                        # search match inside the invisible part of a file name
                        # needs to be addressed separately, but for now it will
                        # suffice to make it less visually disturbing.
                        matchOffset = 0

                    selectionStart = self.getItemStartByte(i) + matchOffset

                    # Set the style for the new match:
                    self.StartStyling(selectionStart, 0xff)
                    stylingRegion = len(searchStr.encode('utf-8'))
                    self.SetStyling(stylingRegion, STYLE_INC_SEARCH)

    def moveItemIntoView(self, items, index):
        item = items[index]
        start_char_on_line = item.start_char_on_line
        endCharOnLine = start_char_on_line + len(item.visible_part)

        if start_char_on_line < self.viewWindow.left:
            # move view window left
            self.viewWindow.left = start_char_on_line
        elif endCharOnLine > self.viewWindow.right():
            # move view window right
            self.viewWindow.left = endCharOnLine - self.viewWindow.width
        else:
            return      # The item is already in view

        self.updateDisplayByItems(items, False)

    def setSelectionOnItem(self, item):
        selectionStart = self.getItemStartByte(item)
        self.SetCurrentPos(selectionStart)
        self.EnsureCaretVisible()

        if item and item.visual_item:
            numCharsToSelect = item.visual_item.vis_len_in_bytes
        else:
            numCharsToSelect = self.charsPerCol

        self.SetSelection(selectionStart, selectionStart + numCharsToSelect)

    def updateSelectedItemLeft(self, selectedItem, numItems):
        numFullLines = numItems % self.viewWindow.height
        bottomRightIndex = self.viewWindow.height * (self.numFullColumns + 1)
        bottomRightIndex -= 1

        if selectedItem % self.viewWindow.height > numFullLines:
            bottomRightIndex = self.viewWindow.height * self.numFullColumns - 1

        return selectedItem - self.viewWindow.height + bottomRightIndex

    def getItemStartByte(self, item):
        # -1 below because I want to get byte count for the lines [0..currLine)
        row = item.coords[1] - 1
        sumBytes = 0

        if row >= 0:
            # +1 below because GetLineEndPosition doesn't account for newlines
            # TODO: why not +row? If it skips newlines, it should have
            # skipped N (=row) of them
            sumBytes = self.GetLineEndPosition(row) + 1

        start_byte_on_line = 0

        if item.visual_item:
            start_byte_on_line = item.visual_item.start_byte_on_line

        return sumBytes + start_byte_on_line

    def applyDefaultStyles(self, rawItems):
        for index, item in enumerate(rawItems):
            if item.visual_item:
                selStart = self.getItemStartByte(item)

                # Note the 0x1f. It means I'm only affecting the style
                # bits, leaving the indicators alone. This avoids having
                # the nasty green squiggle underline.
                self.StartStyling(selStart, 0x1f)

                itemNameLen = item.visual_item.vis_len_in_bytes
                self.SetStyling(itemNameLen, item.style)


class Candy(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, -1, title)

        self.splitter = wx.SplitterWindow(self, ID_SPLITTER,
                                          style=wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize(50)

        display_size = wx.DisplaySize()
        app_size = (display_size[0] / 2, display_size[1] / 2)
        self.SetSize(app_size)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.splitter, 1, wx.EXPAND)
        self.status_line = StatusLine(self, ID_STATUS_LINE, app_size[0],
                                      general_config, color_scheme)
        self.sizer.AddSpacer(2)
        sizer_flags = wx.BOTTOM | wx.ALIGN_BOTTOM | wx.EXPAND
        self.sizer.Add(self.status_line, 0, sizer_flags)
        self.SetSizer(self.sizer)

        self.p1 = PanelController(self.splitter, 'm1.', 'c1.')
        self.p2 = PanelController(self.splitter, 'm2.', 'c2.')
        self.splitter.SplitVertically(self.p1.view, self.p2.view)

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_SPLITTER_DCLICK, self.on_double_click, id=ID_SPLITTER)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_sash_pos_changed,
                  id=ID_SPLITTER)

        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText(os.getcwdu())
        self.Center()
        self.set_active_pane(self.p1)

    def set_active_pane(self, pane):
        self.active_pane = pane
        pane.view.SetFocus()
        self.status_line.set_message_prefix(pane.controllerSignature)

    def setup_and_show(self):
        self.p2.initializeAndShowInitialView()
        self.p1.initializeAndShowInitialView()
        self.set_active_pane(self.p1)

    # XXX: is it ever used?
    def OnExit(self, e):
        self.Close(True)

    def update_panes_on_size(self):
        num_columns = 3

        if self.splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            num_columns = 5

        self.p1.initializeViewSettings(num_columns)
        self.p2.initializeViewSettings(num_columns)

    def split_equal(self):
        size = self.GetSize()

        split_mode = self.splitter.GetSplitMode()
        sash_dimension = size.x

        if split_mode == wx.SPLIT_HORIZONTAL:
            sash_dimension = size.y

        # compensate for the five pixels of sash itself (dammit!)
        sash_dimension -= 5
        self.splitter.SetSashPosition(sash_dimension / 2)
        self.update_panes_on_size()

    def on_size(self, event):
        self.split_equal()
        event.Skip()

    def on_double_click(self, event):
        self.split_equal()

    def on_sash_pos_changed(self, event):
        self.splitter.UpdateSize()
        self.update_panes_on_size()
        event.Skip()

    def switch_pane(self):
        if self.active_pane == self.p1:
            self.set_active_pane(self.p2)
        else:
            self.set_active_pane(self.p1)

    def switch_splitting_mode(self):
        curr_split_mode = self.splitter.GetSplitMode()
        new_split_mode = wx.SPLIT_VERTICAL
        num_columns = 3

        if curr_split_mode == wx.SPLIT_VERTICAL:
            new_split_mode = wx.SPLIT_HORIZONTAL
            num_columns = 5

        self.splitter.SetSplitMode(new_split_mode)
        self.split_equal()
        self.p1.initializeViewSettings(num_columns)
        self.p2.initializeViewSettings(num_columns)


def main():
    app = wx.App(0)
    candy = Candy(None, -1, 'Candy')
    candy.Show()
    candy.setup_and_show()
    app.MainLoop()


if __name__ == '__main__':
    main()

