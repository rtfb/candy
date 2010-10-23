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
import sys
import os

import wx

# Make sure candy/src/ is in the path, so importing works fine
func_tests = os.path.dirname(os.path.join(os.getcwd(), sys.argv[0]))
src = os.path.abspath(os.path.join(func_tests, '../../src'))
sys.path.append(src)

import candy
import util
import data


theApp = None
theFrame = None


class TestMotion(unittest.TestCase):
    def setUp(self):
        # By default, all tests in this case will have this layout of items:
        # two columns, three rows, all full of items ('a' being '..')
        # +-
        # | a d
        # | b e
        # | c f
        # +-
        lst = ['a', 'b', 'c', 'd', 'e']
        data.list_files = lambda a, b: util.list_of_tuples(lst, b)
        self.panel = theFrame.p1
        self.panel.initialize_view_settings(3, 3)
        self.panel.model.fill_list_by_working_dir('.')
        self.panel.move_selection_zero()

    def tearDown(self):
        self.panel.selected_item = 0

    def testMoveRight(self):
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 3)
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 1)
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 4)
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 2)

    def testMoveLeft(self):
        self.panel.move_selection_last()
        self.panel.move_selection_left()
        self.assertEquals(self.panel.selected_item, 2)
        self.panel.move_selection_left()
        self.assertEquals(self.panel.selected_item, 4)
        self.panel.move_selection_left()
        self.assertEquals(self.panel.selected_item, 1)

    def testMoveDown(self):
        self.panel.move_selection_down()
        self.assertEquals(self.panel.selected_item, 1)
        self.panel.move_selection_down()
        self.assertEquals(self.panel.selected_item, 2)
        self.panel.move_selection_down()
        self.assertEquals(self.panel.selected_item, 3)

    def testMoveUp(self):
        self.panel.move_selection_up()
        self.assertEquals(self.panel.selected_item, 5)
        self.panel.move_selection_up()
        self.assertEquals(self.panel.selected_item, 4)
        self.panel.move_selection_up()
        self.assertEquals(self.panel.selected_item, 3)
        self.panel.move_selection_up()
        self.assertEquals(self.panel.selected_item, 2)

    #
    # Layout:
    #
    # +-
    # | a d
    # | b e
    # | c f
    # +-
    #
    # What's going wrong:
    # * When on 'f' and press RIGHT, should go to 'a', but goes to 'd'
    # * When on 'd' and press RIGHT, should go to 'b', but goes to 'a'
    #
    def testFtoA(self):
        self.panel.move_selection_last()
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 0)

    def testDtoB(self):
        self.panel.move_selection_right()
        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 1)

    #
    # Layout:
    #
    # +-
    # | a e i
    # | b f j
    # | c g
    # | d h
    # +-
    #
    # What's going wrong:
    # * When on 'g' and press RIGHT, should go to 'd', but goes to 'a'
    # * When on 'a' and press LEFT, should go to 'j', but goes to 'h'
    #      - that one is actually correct...
    # * When on 'h' and press RIGHT, should go to 'a', but goes to 'e'
    #
    def testGtoD(self):
        lst = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        data.list_files = lambda a, b: util.list_of_tuples(lst, b)
        # Constrain the size, to feed the test data in a controlled manner
        self.panel.initialize_view_settings(3, 4)
        self.panel.model.fill_list_by_working_dir('.')

        # A rather lengthy way to position ourselves on 'g':
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()

        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 3)

    def testAtoH(self):
        lst = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        data.list_files = lambda a, b: util.list_of_tuples(lst, b)
        # Constrain the size, to feed the test data in a controlled manner
        self.panel.initialize_view_settings(3, 4)
        self.panel.model.fill_list_by_working_dir('.')

        self.panel.move_selection_left()
        self.assertEquals(self.panel.selected_item, 7)

    def testHtoA(self):
        lst = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
        data.list_files = lambda a, b: util.list_of_tuples(lst, b)
        # Constrain the size, to feed the test data in a controlled manner
        self.panel.initialize_view_settings(3, 4)
        self.panel.model.fill_list_by_working_dir('.')

        # A rather lengthy way to position ourselves on 'h':
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()
        self.panel.move_selection_down()

        self.panel.move_selection_right()
        self.assertEquals(self.panel.selected_item, 0)


def suite():
    motion_suite = unittest.makeSuite(TestMotion, 'test')
    return unittest.TestSuite([motion_suite])


if __name__ == '__main__':
    theApp = wx.PySimpleApp()
    theFrame = candy.Candy(None, -1, 'foo')

    # Let application know its dimensions
    theFrame.Show(True)
    theFrame.Show(False)

    # Now when dimensions are known, let's proceed initializing
    theFrame.setup_and_show()

    # Speed up the tests by not executing update_view()
    theFrame.p1.update_view = lambda: None

    # Constrain the size, to feed the test data in a controlled manner
    theFrame.p1.initialize_view_settings(3, 3)

    unittest.main(defaultTest='suite')

