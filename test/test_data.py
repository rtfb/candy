#!/usr/bin/env python
#
#   Copyright (C) 2009 Vytautas Saltenis.
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
import sys

sys.path.append(os.path.abspath('../src'))

import data
import util


data.list_files = util.fake_file_lister


class TestModel(unittest.TestCase):
    def setUp(self):
        self.model = data.PanelModel('m.')

    def tearDown(self):
        pass

    def testInitialDirectoryOnActivePane(self):
        homeDir = os.path.expanduser('~')
        self.assertEqual(self.model.working_dir, homeDir)

    def testItemListIsEmpty(self):
        self.assertEquals(len(self.model.items), 0)

    def testFillItemsList(self):
        self.model.fill_list_by_working_dir('.')
        # -5 here because the fake list contains 5 hidden files
        fakeListLen = len(util.fake_file_lister(False, '.')) - 5
        self.assertEquals(len(self.model.items), fakeListLen)

    def testUpdirFromFlatView(self):
        self.model.fill_list_by_working_dir('.')
        self.model.flatten_directory()
        self.assertEquals(self.model.updir(), 0)

    def testNextSearchMatchDoesNotOverflowWhenNearEnd(self):
        onePastLast = len(self.model.items)
        match = self.model.next_search_match('no_such_match', onePastLast)
        self.assertEquals(match, 0)

    def testSetDirFilter(self):
        self.model.set_dir_filter('a')

        if self.model.directory_view_filter is None:
            self.assertFalse()


def suite():
    modelSuite = unittest.makeSuite(TestModel, 'test')
    return unittest.TestSuite([modelSuite])


if __name__ == '__main__':
    unittest.main(defaultTest='suite')

