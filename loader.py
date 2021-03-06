#!/usr/bin/env python3
# -*- coding: utf-8 -*-

' dataset module for EVVE '

__author__ = 'fyang'

import os
import glob
import utils


class Loader(object):
    '''
    A loader class for EVVE dataset
    '''

    def __init__(self, infos_dir, event, tag):
        '''
        tag is 'qr' or 'db'
        '''
        self.event = event
        self.tag = tag
        self.dir = '{0}/{1}_{2}'.format(infos_dir, event, tag)
        self.paths = glob.glob(os.path.join(self.dir, '*.jbl'))
        self.video_num = len(self.paths)
        self.nexti = 0

    def __len__(self):
        return self.video_num

    def __iter__(self):
        return self

    def __getitem__(self, key):
        if type(key) is int:
            path = self.paths[key]
        elif type(key) is str:
            path = '{0}/{1}.jbl'.format(self.dir, key)
        return utils.load(path)

    def __next__(self):
        self.nexti += 1
        if self.nexti > self.video_num:
            raise StopIteration()
        return self.__getitem__(self.nexti - 1)

