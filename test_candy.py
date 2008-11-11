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

import unittest
import candy
import wx
import os
import pdb

def fakeFileLister (isFlatDirectoryView, cwd):
    dirs = []
    files = []
    hidden = []

    for i in range (10):
        dirs.append ('dir' + str (i))

    dirs.insert (0, '..')

    for i in range (20):
        files.append ('file' + str (i))

    for i in range (5):
        hidden.append ('.hid' + str (i))

    return dirs + files + hidden

candy.listFiles = fakeFileLister

class TestSmartJustifier (unittest.TestCase):
    def setUp (self):
        pass

    def tearDown (self):
        pass

    def testBasicJustification (self):
        sj = candy.SmartJustifier (5)
        self.assertEquals ('abc  ', sj.justify ('abc'))

    def testDotsInTheMiddle (self):
        target = 'long...name.txt'
        sj = candy.SmartJustifier (len (target))
        self.assertEquals (target, sj.justify ('longTHIS_SHOULD_GET_REMOVEDname.txt'))

    def testOddNumberOfCharsAndDots (self):
        target = 'long...ame.txt'
        sj = candy.SmartJustifier (len (target))
        self.assertEquals (target, sj.justify ('longTHIS_SHOULD_GET_REMOVEDame.txt'))

    def testEmptyLine (self):
        sj = candy.SmartJustifier (3)
        self.assertEquals ('   ', sj.justify (''))

    def testOneChar (self):
        sj = candy.SmartJustifier (3)
        self.assertEquals ('a  ', sj.justify ('a'))

    def testWidth (self):
        targetWidth = 10
        sj = candy.SmartJustifier (targetWidth)
        self.assertEquals (targetWidth, len (sj.justify ('0123456789.gnumeric')))
        self.assertEquals (targetWidth, len (sj.justify ('Jim_Hefferon_-_Linear_Algebra.pdf')))
        self.assertEquals (targetWidth, len (sj.justify ('a')))

    def testGnumeric (self):
        target = '0...9.gnumeri'
        sj = candy.SmartJustifier (len (target))
        self.assertEquals (target, sj.justify ('0123456789.gnumeric'))

class TestCandy (unittest.TestCase):
    def setUp (self):
        self.app = wx.PySimpleApp ()
        self.frame = candy.Candy (None, -1, 'foo')

        # Let application know its dimensions
        self.frame.Show (True)
        self.frame.Show (False)

        # Now when dimensions are known, lets proceed initializing
        self.frame.setUpAndShow ()

    def tearDown (self):
        self.frame.Destroy ()

    def testSplitEqual (self):
        size = self.frame.GetSize ()
        # -5 is to compensate for the sash width of 5 pixels. Same in the code.
        self.assertEqual ((size.x - 5) / 2, self.frame.splitter.GetSashPosition ())

    def testInitialDirectoryOnActivePane (self):
        self.assertEqual (self.frame.activePane.workingDir, os.path.expanduser ('~'))

    def testInitialSelection (self):
        self.assertEqual (self.frame.activePane.selectedItem, 0)

    def testItemListIsEmpty (self):
        self.frame.p1.clearList ()
        self.frame.p2.clearList ()
        self.assertEquals (len (self.frame.p1.items), 0)
        self.assertEquals (len (self.frame.p2.items), 0)

    def testSelectionDoesntGetAnywhereOnEmptyList (self):
        self.frame.p1.clearList ()
        self.frame.p2.clearList ()
        self.frame.p1.moveSelectionUp ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionDown ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionLeft ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionRight ()
        self.assertEquals (self.frame.p1.selectedItem, 0)

    def testItemStartCharIsZeroOnEmptyList (self):
        self.assertEquals (self.frame.p1.items[0].visualItem.startCharOnLine, 0)

    def testItemsListIsNotEmpty (self):
        self.assertTrue (len (self.frame.p1.items) > 0)

    def testSimpleIncSearch (self):
        self.frame.p1.incrementalSearch ('dir')
        self.assertEquals (self.frame.p1.searchMatchIndex, 1)

    def testNextSearchMatch (self):
        searchStr = 'file'
        self.frame.p1.incrementalSearch (searchStr)
        currPos = self.frame.p1.searchMatchIndex
        match = self.frame.p1.nextSearchMatch (searchStr, self.frame.p1.searchMatchIndex + 1)
        self.assertEquals (match, currPos + 1)

    def testItemStartCharOnLine (self):
        self.assertEquals (self.frame.p1.items[0].visualItem.startCharOnLine, 0)

        for index in range (len (self.frame.p1.items)):
            col = self.frame.p1.items[index].coords[0]
            # 11 is a magic column width number here. Based on last evidence
            # that works.
            self.assertEquals (self.frame.p1.items[index].visualItem.startCharOnLine, col * 11)

    def testItemStartChar (self):
        #pdb.set_trace ()
        self.assertEquals (self.frame.p1.getItemStartByte (0), 0)

        for index in range (len (self.frame.p1.items)):
            # 36 is a magic ViewWindow.width number here. Based on last
            # evidence that works. Only works out for the 0th column, so this
            # test will be failing for now, until I get rid of this magic.
            # Also, getItemStartByte only works in this ASCII test case.
            self.assertEquals (self.frame.p1.getItemStartByte (index), index * 36)

def suite ():
    import test_keyboard
    candySuite = unittest.makeSuite (TestCandy, 'test')
    smartJustifierSuite = unittest.makeSuite (TestSmartJustifier, 'test')
    keyboardSuite = unittest.makeSuite (test_keyboard.TestKeyboardEventHandler)
    return unittest.TestSuite ([smartJustifierSuite, keyboardSuite, candySuite])

if __name__ == '__main__':
    unittest.main (defaultTest = 'suite')

