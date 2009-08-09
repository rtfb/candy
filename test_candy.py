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
import os
import pdb

import wx

import candy
import util
import data


data.list_files = util.fake_file_lister


class TestFileLister(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testNoItemsGetLost(self):
        ret = data.collect_list_info(False, u'.')
        self.assertEquals(len(ret), len(util.fake_file_lister(False, u'.')))

    def testItemName(self):
        ret = data.collect_list_info(False, u'.')
        self.assertEquals(ret[0].fileName, u'..')


class TestListFiltering(unittest.TestCase):
    def setUp(self):
        allItems = data.collect_list_info(False, u'.')
        self.list = data.construct_list_for_filling(allItems, None)

    def tearDown(self):
        pass

    def testNothingHiddenRemains(self):
        """Nothing should start with a dot, except for the '..'
        """

        for i in self.list[1:]:
            self.assertFalse(i.fileName.startswith(u'.'))

    def testOnlyDirsInFront(self):
        def looks_like_dir(str):
            return str.startswith(u'dir') or str == u'..'

        for item in self.list:
            if not looks_like_dir(item.fileName):
                break

            self.assertTrue(looks_like_dir(item.fileName))


class TestSmartJustifier(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testBasicJustification(self):
        sj = candy.SmartJustifier(5)
        self.assertEquals('abc  ', sj.justify('abc'))

    def testDotsInTheMiddle(self):
        target = 'long...name.txt'
        sj = candy.SmartJustifier(len(target))
        longFileName = 'longTHIS_SHOULD_GET_REMOVEDname.txt'
        self.assertEquals(target, sj.justify(longFileName))

    def testOddNumberOfCharsAndDots(self):
        target = 'long...ame.txt'
        sj = candy.SmartJustifier(len(target))
        longFileName = 'longTHIS_SHOULD_GET_REMOVEDname.txt'
        self.assertEquals(target, sj.justify(longFileName))

    def testEmptyLine(self):
        sj = candy.SmartJustifier(3)
        self.assertEquals('   ', sj.justify(''))

    def testOneChar(self):
        sj = candy.SmartJustifier(3)
        self.assertEquals('a  ', sj.justify('a'))

    def testWidth(self):
        targetWidth = 10
        sj = candy.SmartJustifier(targetWidth)
        testCases = ['0123456789.gnumeric',
                     'Jim_Hefferon_-_Linear_Algebra.pdf',
                     'a']
        for tc in testCases:
            self.assertEquals(targetWidth, len(sj.justify(tc)))

    def testGnumeric(self):
        target = '0...9.gnumeri'
        sj = candy.SmartJustifier(len(target))
        self.assertEquals(target, sj.justify('0123456789.gnumeric'))


class TestCandy(unittest.TestCase):
    def setUp(self):
        self.app = wx.PySimpleApp()
        self.frame = candy.Candy(None, -1, 'foo')

        # Let application know its dimensions
        self.frame.Show(True)
        self.frame.Show(False)

        # Now when dimensions are known, let's proceed initializing
        self.frame.setUpAndShow()

        # Speed up the tests by not executing updateView()
        self.frame.p1.updateView = lambda: None
        self.frame.p2.updateView = lambda: None

    def tearDown(self):
        self.frame.Destroy()

    def testSplitEqual(self):
        size = self.frame.GetSize()
        # -5 is to compensate for the sash width of 5 pixels. Same in the code.
        sashPos = self.frame.splitter.GetSashPosition()
        self.assertEqual((size.x - 5) / 2, sashPos)

    def testInitialSelection(self):
        self.assertEqual(self.frame.activePane.selectedItem, 0)

    def testItemListIsEmpty(self):
        self.frame.p1.clearList()
        self.frame.p2.clearList()
        self.assertEquals(len(self.frame.p1.model.items), 0)
        self.assertEquals(len(self.frame.p2.model.items), 0)

    def testSelectionDoesntGetAnywhereOnEmptyList(self):
        c1 = self.frame.p1
        c2 = self.frame.p2
        c1.clearList()
        c2.clearList()
        c1.moveSelectionUp()
        self.assertEquals(c1.selectedItem, 0)
        c1.moveSelectionDown()
        self.assertEquals(c1.selectedItem, 0)
        c1.moveSelectionLeft()
        self.assertEquals(c1.selectedItem, 0)
        c1.moveSelectionRight()
        self.assertEquals(c1.selectedItem, 0)

    def testItemStartCharIsZeroOnEmptyList(self):
        item = self.frame.p1.model.items[0]
        self.assertEquals(item.visualItem.startCharOnLine, 0)

    def testItemsListIsNotEmpty(self):
        self.assertTrue(len(self.frame.p1.model.items) > 0)

    def testSimpleIncSearch(self):
        self.assertEquals(self.frame.p1.incrementalSearch('dir'), 1)

    def testNextSearchMatch(self):
        searchStr = 'file'
        currPos = self.frame.p1.incrementalSearch(searchStr)
        match = self.frame.p1.model.nextSearchMatch(searchStr, currPos + 1)
        self.assertEquals(match, currPos + 1)

    def testItemStartCharOnLine(self):
        item = self.frame.p1.model.items[0]
        self.assertEquals(item.visualItem.startCharOnLine, 0)

        for item in self.frame.p1.model.items:
            col = item.coords[0]
            # 11 is a magic column width number here. Based on last evidence
            # that works.
            self.assertEquals(item.visualItem.startCharOnLine, col * 11)

    def testItemStartChar(self):
        item = self.frame.p1.model.items[0]
        view = self.frame.p1.view
        self.assertEquals(view.getItemStartByte(item), 0)

        for index, item in enumerate(self.frame.p1.model.items):
            # 36 is a magic ViewWindow.width number here. Based on last
            # evidence that works. Because of this magic, getItemStartByte
            # only works in this ASCII test case.
            column, row = item.coords
            referenceValue = view.charsPerCol * column + 36 * row
            self.assertEquals(view.getItemStartByte(item), referenceValue)

    def testHandleKeyEventDoesNothingOnBadKey(self):
        panel = self.frame.p1
        temp = panel.setSelectionOnCurrItem
        panel.setSelectionOnCurrItem = None

        try:
            # XXX: there should not be such a code and mod combo:
            panel.handleKeyEvent(0, 0)
        except TypeError as e:
            self.assertEquals(e.what(), "'NoneType' object is not callable")

        panel.setSelectionOnCurrItem = temp

    def testRefreshReadsDisk(self):
        data.list_files = util.failing_file_lister

        try:
            self.frame.p1.refresh()
            self.assertTrue(False)
        except RuntimeError as e:
            self.assertEquals(str(e), 'blerk')

        data.list_files = util.fake_file_lister

    def testGetSelection(self):
        self.assertEquals(self.frame.p1.getSelection().fileName, '..')

    def testRefreshMaintainsPosition(self):
        panel = self.frame.p1
        panel.handleKeyEvent(ord('J'), None)
        panel.handleKeyEvent(ord('J'), None)
        panel.handleKeyEvent(ord('J'), None)
        file = panel.getSelection().fileName
        panel.refresh()
        self.assertEquals(file, panel.getSelection().fileName)


class TestCandyWithSingleColumn(unittest.TestCase):
    def setUp(self):
        self.app = wx.PySimpleApp()
        self.frame = candy.Candy(None, -1, 'foo')

        # Let application know its dimensions
        self.frame.Show(True)
        self.frame.Show(False)

        data.list_files = util.fake_file_lister2

        # Now when dimensions are known, let's proceed initializing
        self.frame.setUpAndShow()

        # Speed up the tests by not executing updateView()
        self.frame.p1.updateView = lambda: None
        self.frame.p2.updateView = lambda: None

    def tearDown(self):
        data.list_files = util.fake_file_lister
        self.frame.Destroy()

    def testMoveRightOnSingleColumnMovesDown(self):
        panel = self.frame.p1
        panel.handleKeyEvent(ord('L'), None)
        self.assertEquals('dir0', panel.getSelection().fileName)

    def testMoveRightOnLastItemMovesToFirst(self):
        panel = self.frame.p1
        panel.handleKeyEvent(ord('9'), None)
        panel.handleKeyEvent(ord('L'), None)
        self.assertEquals('..', panel.getSelection().fileName)

    def testMoveLeftOnFirstItemMovesToLast(self):
        panel = self.frame.p1
        panel.handleKeyEvent(ord('0'), None)
        panel.handleKeyEvent(ord('H'), None)

        # This is a double test here: the first test is what I actually want to
        # know, and the second one makes sure I don't get fooled by Python's
        # ability to subscribe lists with negative indices
        self.assertEquals('file2', panel.getSelection().fileName)
        self.assertEquals(len(panel.model.items) - 1, panel.selectedItem)

    def testNumItems(self):
        panel = self.frame.p1
        self.assertEquals(panel.numItems(), len(panel.model.items))


def suite():
    import test_keyboard
    import test_data
    candySuite = unittest.makeSuite(TestCandy, 'test')
    candySuiteSingleCol = unittest.makeSuite(TestCandyWithSingleColumn, 'test')
    modelSuite = unittest.makeSuite(test_data.TestModel, 'test')
    smartJustifierSuite = unittest.makeSuite(TestSmartJustifier, 'test')
    keyboardSuite = unittest.makeSuite(test_keyboard.TestKeyboardEventHandler)
    fileListerSuite = unittest.makeSuite(TestFileLister)
    listFiltererSuite = unittest.makeSuite(TestListFiltering)
    return unittest.TestSuite([smartJustifierSuite, keyboardSuite,
                               modelSuite, candySuite, candySuiteSingleCol,
                               fileListerSuite, listFiltererSuite])


def fast():
    import test_keyboard
    import test_data
    modelSuite = unittest.makeSuite(test_data.TestModel, 'test')
    smartJustifierSuite = unittest.makeSuite(TestSmartJustifier, 'test')
    keyboardSuite = unittest.makeSuite(test_keyboard.TestKeyboardEventHandler)
    fileListerSuite = unittest.makeSuite(TestFileLister)
    listFiltererSuite = unittest.makeSuite(TestListFiltering)
    return unittest.TestSuite([smartJustifierSuite, keyboardSuite,
                               modelSuite, fileListerSuite,
                               listFiltererSuite])



if __name__ == '__main__':
    import sys
    if len(sys.argv) > 0 and sys.argv[0] == 'fast':
        unittest.main(defaultTest='fast')
    else:
        unittest.main(defaultTest='suite')

