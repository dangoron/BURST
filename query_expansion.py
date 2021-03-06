#!/usr/bin/env python3
# -*- coding: utf-8 -*-

' TE query expansion module '

__author__ = 'fyang'

import argparse
import numpy as np
import retrieve
import joblib
from joblib import Parallel, delayed
from itertools import combinations
from collections import Counter
import utils


# global data kept for parallel processes
global_qr_data = ''
global_results = ''


def get_new_query(qr_datum_index):
    '''
    Generate new query with given query datum index
    '''
    qr_datum = global_qr_data[qr_datum_index]
    qr_results = (_ for _ in global_results if _['qrname'] == qr_datum['name'])
    qr_results = sorted(qr_results, key=lambda _: _['score'], reverse=True)
    short_list = get_short_list(qr_results[:short_list_len])
    consistent_list = check_consistency(short_list)
    subtract_vectors = get_subtract_vectors(
        qr_results[short_list_len:][:far_list_len])
    new_query = {
        'event': qr_datum['event'],
        'name': qr_datum['name'],
        'length': qr_datum['length']
    }
    for period in periods:
        new_query[period] = qr_datum[period]
        new_query[period][0] += np.sum([_[period][0]
                                        for _ in short_list], axis=0)
        new_query[period][0] /= 1 + short_list_len
        new_query[period][1:] += np.sum([_[period][1:]
                                         for _ in consistent_list], axis=0)
        new_query[period][1:] /= 1 + len(consistent_list)
        new_query[period] -= subtract_vectors[period]
    return new_query


def check_consistency(short_list):
    '''
    Check temporal consistency on short list, and shift consistent videos.
    Return consistent videos' indices in short list.
    '''
    # marks for denoting clusters
    marks = np.arange(short_list_len)
    for i, j in combinations(range(short_list_len), 2):
        # offset between query video and database video 1
        offset1 = short_list[i]['offset']
        # offset between query video and database video 2
        offset2 = short_list[j]['offset']
        # offset between database video 1 and database video 2
        offset3 = retrieve.get_result(short_list[i], short_list[j])['offset']
        if np.abs(offset1 - offset2 + offset3) > epsilon:
            continue
        minimum = min(marks[i], marks[j])
        marks[i] = minimum
        marks[j] = minimum
    clusters = Counter(marks)
    # marks of cluster where videos are consistent
    consistent_marks = [_ for _ in clusters if clusters[_] > 1]
    indices = [i for i, j in enumerate(marks) if j in consistent_marks]
    # shift videos who are consistent to align on the original query
    for i in indices:
        for period in periods:
            offset = short_list[i]['offset']
            short_list[i][period] = \
                shift_video_descriptor(short_list[i][period], period, offset)
    return [short_list[i] for i in indices]


def get_short_list(short_results):
    '''
    Get short list
    '''
    short_list = []
    for event in set([_['dbevent'] for _ in short_results]):
        database = load_event_database(event)
        for result in (_ for _ in short_results if _['dbevent'] == event):
            datum = next(_ for _ in database if _['name'] == result['dbname'])
            # add offset to original query
            datum['offset'] = result['offset']
            short_list.append(datum)
    return short_list


def get_subtract_vectors(far_results):
    '''
    Get vector to be subtracted in DoN strategy by using far results
    '''
    vectors = {}
    for period in periods:
        vectors[period] = 0
    number = 0
    for event in range(1, 14):
        database = load_event_database(event)
        for result in (_ for _ in far_results if _['dbevent'] == event):
            datum = next(_ for _ in database if _['name'] == result['dbname'])
            for period in periods:
                vectors[period] += datum[period]
            number += 1
    for period in periods:
        vectors[period] /= number
    return vectors


def load_event_database(event):
    '''
    Load video descriptors in database for a given event
    '''
    path = '{0}/{1}_db.jbl'.format(data_dir, event)
    with open(path, 'rb') as database_file:
        database = joblib.load(database_file)
    return database


def shift_video_descriptor(descriptor, period, offset):
    '''
    Shift the video descriptor by given offset on particular period
    '''
    freq_num = int((descriptor.size / frame_desc_dim - 1) / 2)
    rotation = - offset / period * 2 * np.pi
    inner_coefs = np.arange(1, freq_num+1).reshape(-1, 1)
    cos_rot = np.cos(rotation * inner_coefs)
    sin_rot = np.sin(rotation * inner_coefs)
    cos_part = descriptor[1:freq_num+1]
    sin_part = descriptor[freq_num+1:]
    shifted_descriptor = np.zeros(descriptor.shape)
    shifted_descriptor[0] = descriptor[0]
    shifted_descriptor[1:freq_num+1] = cos_part * cos_rot - sin_part * sin_rot
    shifted_descriptor[freq_num+1:] = sin_part * cos_rot + cos_part * sin_rot
    return shifted_descriptor


class QueryExpansion(object):
    def __init__(self, embed_dir, results_dir):
        self.embed_dir = embed_dir
        self.results_dir = results_dir

    def __call__(self, events, iterations):
        '''
        Conduct query expansion on given events
        '''
        for iteration in iterations:
            for qr_event in events:
                qr_data = self.get_new_queries(qr_event, iteration)
                retrieve.retrieve_event(
                    qr_event, range(1, 14), qr_data, iteration)

    def get_new_queries(self, event, iteration):
        '''
        Generate new queries for a given event
        '''
        global global_qr_data, global_results
        # load query data
        global_qr_data = utils.load(
            '{}/{}_qr.jbl'.format(self.embed_dir, event))
        # load this event's previous retrieval results
        global_results = utils.load('{}/{}_{}.jbl'.format(self.results_dir,
                                                          event, iteration-1))
        qr_data_num = len(global_qr_data)
        new_queries = Parallel(
            n_jobs=-1)([delayed(get_new_query)(i) for i in range(qr_data_num)])
        return new_queries


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--embed_dir', type=str,
                        help="directory to embeddings")
    parser.add_argument('--results_dir', type=str,
                        help="directory to results")
    parser.add_argument('--periods', type=int, nargs='+',
                        help="list of periods")
    parser.add_argument('--short_list_len', type=int, default=10,
                        help="length of short list")
    parser.add_argument('--far_list_len', type=int, default=2000,
                        help="length of far list")
    parser.add_argument('--epsilon', type=int, default=10,
                        help="parameter epsilon for consistency check")
    args = parser.parse_args()
    short_list_len = args.short_list_len
    far_list_len = args.far_list_len
    epsilon = args.epsilon
    periods = args.periods
    expansion = QueryExpansion(args.embed_dir, args.results_dir)
    expansion(range(1, 14), [1, 2, 3])
