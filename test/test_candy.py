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
import sys

sys.path.append(os.path.abspath('../src'))

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
        self.assertEquals(ret[0].file_name, u'..')


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
            self.assertFalse(i.file_name.startswith(u'.'))

    def testOnlyDirsInFront(self):
        def looks_like_dir(str):
            return str.startswith(u'dir') or str == u'..'

        for item in self.list:
            if not looks_like_dir(item.file_name):
                break

            self.assertTrue(looks_like_dir(item.file_name))


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
        self.frame.setup_and_show()

        # Speed up the tests by not executing update_view()
        self.frame.p1.update_view = lambda: None
        self.frame.p2.update_view = lambda: None

    def tearDown(self):
        self.frame.Destroy()

    def testSplitEqual(self):
        size = self.frame.GetSize()
        # -5 is to compensate for the sash width of 5 pixels. Same in the code.
        sashPos = self.frame.splitter.GetSashPosition()
        self.assertEqual((size.x - 5) / 2, sashPos)

    def testInitialSelection(self):
        self.assertEqual(self.frame.active_pane.selected_item, 0)

    def testSelectionDoesntGetAnywhereOnEmptyList(self):
        c1 = self.frame.p1
        c2 = self.frame.p2
        c1.clear_list()
        c2.clear_list()
        c1.move_selection_up()
        self.assertEquals(c1.selected_item, 0)
        c1.move_selection_down()
        self.assertEquals(c1.selected_item, 0)
        c1.move_selection_left()
        self.assertEquals(c1.selected_item, 0)
        c1.move_selection_right()
        self.assertEquals(c1.selected_item, 0)

    def testItemStartCharIsZeroOnEmptyList(self):
        item = self.frame.p1.model.items[0]
        self.assertEquals(item.visual_item.start_char_on_line, 0)

    def testItemsListIsNotEmpty(self):
        self.assertTrue(len(self.frame.p1.model.items) > 0)

    def testSimpleIncSearch(self):
        self.assertEquals(self.frame.p1._incremental_search('dir'), 1)

    def testNextSearchMatch(self):
        searchStr = 'file'
        currPos = self.frame.p1._incremental_search(searchStr)
        match = self.frame.p1.model.next_search_match(searchStr, currPos + 1)
        self.assertEquals(match, currPos + 1)

    def testItemStartCharOnLine(self):
        item = self.frame.p1.model.items[0]
        self.assertEquals(item.visual_item.start_char_on_line, 0)

        for item in self.frame.p1.model.items:
            col = item.coords[0]
            # 11 is a magic column width number here. Based on last evidence
            # that works.
            self.assertEquals(item.visual_item.start_char_on_line, col * 11)

    def testItemStartChar(self):
        item = self.frame.p1.model.items[0]
        view = self.frame.p1.view
        self.assertEquals(view._get_item_start_byte(item), 0)

        for index, item in enumerate(self.frame.p1.model.items):
            # 36 is a magic ViewWindow.width number here. Based on last
            # evidence that works. Because of this magic, _get_item_start_byte
            # only works in this ASCII test case.
            column, row = item.coords
            reference_value = view._chars_per_col * column + 36 * row
            self.assertEquals(view._get_item_start_byte(item), reference_value)

    def testGetSelection(self):
        self.assertEquals(self.frame.p1._get_selection().file_name, '..')

    def testRefreshMaintainsPosition(self):
        panel = self.frame.p1
        panel._handle_key_event(ord('J'), None)
        panel._handle_key_event(ord('J'), None)
        panel._handle_key_event(ord('J'), None)
        file = panel._get_selection().file_name
        panel.refresh()
        self.assertEquals(file, panel._get_selection().file_name)


class TestCandyWithSingleColumn(unittest.TestCase):
    def setUp(self):
        self.app = wx.PySimpleApp()
        self.frame = candy.Candy(None, -1, 'foo')

        # Let application know its dimensions
        self.frame.Show(True)
        self.frame.Show(False)

        data.list_files = util.fake_file_lister2

        # Now when dimensions are known, let's proceed initializing
        self.frame.setup_and_show()

        # Speed up the tests by not executing update_view()
        self.frame.p1.update_view = lambda: None
        self.frame.p2.update_view = lambda: None

    def tearDown(self):
        data.list_files = util.fake_file_lister
        self.frame.Destroy()

    def testMoveRightOnSingleColumnMovesDown(self):
        panel = self.frame.p1
        panel._handle_key_event(ord('L'), None)
        self.assertEquals('dir0', panel._get_selection().file_name)

    def testMoveRightOnLastItemMovesToFirst(self):
        panel = self.frame.p1
        panel._handle_key_event(ord('9'), None)
        panel._handle_key_event(ord('L'), None)
        self.assertEquals('..', panel._get_selection().file_name)

    def testMoveLeftOnFirstItemMovesToLast(self):
        panel = self.frame.p1
        panel._handle_key_event(ord('0'), None)
        panel._handle_key_event(ord('H'), None)

        # This is a double test here: the first test is what I actually want to
        # know, and the second one makes sure I don't get fooled by Python's
        # ability to subscribe lists with negative indices
        self.assertEquals('file2', panel._get_selection().file_name)
        self.assertEquals(len(panel.model.items) - 1, panel.selected_item)

    def testNumItems(self):
        panel = self.frame.p1
        self.assertEquals(panel._num_items(), len(panel.model.items))


class TestLocationHistory(unittest.TestCase):
    def setUp(self):
        self.loc_hist = candy.LocationHistory()

    def test_loc_hist_empty(self):
        self.assertEquals(len(self.loc_hist), 0)

    def test_empty_get_does_not_crash(self):
        try:
            self.loc_hist.get()
        except:
            self.fail()

    def test_empty_get_returns_home(self):
        self.assert_(self.loc_hist.get() == '~')

    def test_loc_hist_grows(self):
        self.loc_hist.push('a')
        self.assertEquals(len(self.loc_hist), 1)

    def test_get_value(self):
        self.loc_hist.push('a')
        self.assertEquals(self.loc_hist.get(), 'a')

    def test_initial_position(self):
        self.assertEqual(self.loc_hist.position, -1)

    def test_push_pushes_position(self):
        self.loc_hist.push('a')
        self.assertEqual(self.loc_hist.position, 0)
        self.loc_hist.push('b')
        self.assertEqual(self.loc_hist.position, 1)

    def test_push_affects_get(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.assertEquals(self.loc_hist.get(), 'b')

    def test_get_depends_on_position(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.push('c')
        self.loc_hist.back()
        self.failUnless(self.loc_hist.get() == 'b')

    def test_go_back(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.back()
        self.assertEquals(self.loc_hist.get(), 'a')

    def test_go_back_does_not_shrink(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.back()
        self.assertEquals(len(self.loc_hist), 2)

    def test_go_back_cycles(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.back()
        self.assertEqual(self.loc_hist.get(), 'a')
        self.assertEqual(self.loc_hist.position, 0)
        self.loc_hist.back()
        self.assertEqual(self.loc_hist.get(), 'b')
        self.assertEqual(self.loc_hist.position, 1)
        self.loc_hist.back()
        self.assertEqual(self.loc_hist.get(), 'a')
        self.assertEqual(self.loc_hist.position, 0)

    def test_push_the_same_does_not_grow(self):
        self.loc_hist.push('a')
        self.loc_hist.push('a')
        self.assertEqual(len(self.loc_hist.container), 1)

    def test_go_forth(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.back()
        self.loc_hist.forth()
        self.assertEquals(self.loc_hist.get(), 'b')

    def test_go_forth_cycles(self):
        self.loc_hist.push('a')
        self.loc_hist.push('b')
        self.loc_hist.forth()
        self.assertEqual(self.loc_hist.get(), 'a')
        self.assertEqual(self.loc_hist.position, 0)
        self.loc_hist.forth()
        self.assertEqual(self.loc_hist.get(), 'b')
        self.assertEqual(self.loc_hist.position, 1)
        self.loc_hist.forth()
        self.assertEqual(self.loc_hist.get(), 'a')
        self.assertEqual(self.loc_hist.position, 0)


class TestPanelController(unittest.TestCase):
    def setUp(self):
        sink = candy.PanelSink()
        self.controller = candy.PanelController(sink, '', '')

    def tearDown(self):
        pass

    def testChangeDirCatchesException(self):
        backup = os.chdir
        def thrower(path):
            raise OSError('foo', 'bar')
        os.chdir = thrower

        try:
            self.controller._change_dir('')
        except:
            self.assert_(False)

        os.chdir = backup

    def testHandleKeyEventDoesNothingOnBadKey(self):
        panel = self.controller
        temp = panel._set_selection_on_curr_item
        panel._set_selection_on_curr_item = None

        try:
            # XXX: there should not be such a code and mod combo:
            panel._handle_key_event(0, 0)
        except TypeError, e:
            self.assertEquals(e.what(), "'NoneType' object is not callable")
        finally:
            panel._set_selection_on_curr_item = temp

    def testRefreshReadsDisk(self):
        data.list_files = util.failing_file_lister

        try:
            self.controller.refresh()
            self.assert_(False)
        except RuntimeError, e:
            self.assertEquals(str(e), 'blerk')
        finally:
            data.list_files = util.fake_file_lister


def make_fast_suite():
    import test_keyboard
    import test_data

    model_suite = unittest.makeSuite(test_data.TestModel, 'test')
    smart_justifier_suite = unittest.makeSuite(TestSmartJustifier, 'test')
    keyboard_suite = test_keyboard.suite()
    file_lister_suite = unittest.makeSuite(TestFileLister)
    list_filterer_suite = unittest.makeSuite(TestListFiltering)
    loc_hist_suite = unittest.makeSuite(TestLocationHistory)
    panel_controller_suite = unittest.makeSuite(TestPanelController)
    return [model_suite, smart_justifier_suite, keyboard_suite,
            file_lister_suite, list_filterer_suite, loc_hist_suite,
            panel_controller_suite]


def suite():
    candy_suite = unittest.makeSuite(TestCandy, 'test')
    single_col_suite = unittest.makeSuite(TestCandyWithSingleColumn, 'test')
    return unittest.TestSuite(make_fast_suite() +
                              [candy_suite, single_col_suite])


def fast():
    return unittest.TestSuite(make_fast_suite())


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 0 and sys.argv[0] == 'fast':
        unittest.main(defaultTest='fast')
    else:
        unittest.main(defaultTest='suite')

