'''
This little script downloads the market price and volume traded day to day to
show how the top coins change over time.  The intention is to analyze how this
measure behaves given historical data.
'''

import datetime
import logging
import json
import multiprocessing
import pprint
import re
import sys
import time

import requests

API_KEY = '0BbG9UxZhOvmEHdfSHAOtUlAN3RoBd'
HOSTNAME = 'https://www.worldcoinindex.com'

LOGGER = logging.getLogger()

DELAY_FOR_INVITATION = 10*5
DELAY_FOR_EVICTION = 7*5


def configure_logging():
    '''
    Configures logging for this module
    '''
    LOGGER.setLevel(logging.DEBUG)
    channel = logging.StreamHandler(sys.stdout)
    channel.setLevel(logging.DEBUG)
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    channel.setFormatter(formatter)
    LOGGER.addHandler(channel)


def get_markets():
    '''
    Gives the current known cryptocoins and their market rate
    '''
    endpoint = 'apiservice/getmarkets'
    params = {
        'fiat': 'usd',
        'key': API_KEY,
    }
    url = '{}/{}'.format(HOSTNAME, endpoint)
    response = requests.get(url, params)
    response.raise_for_status()
    return json.loads(response.text)['Markets'][0]


def get_coin_names():
    '''
    Fetches all the tickers of the coins being tracked
    '''
    LOGGER.debug('Getting coin names')
    markets = get_markets()
    return [re.sub(r'\/BTC$', '', market['Name']) for market in markets]


def get_history(name, days=30):
    '''
    Returns historical data given the name of the coin
    '''
    LOGGER.debug('Getting history for %s', name)
    endpoint = 'home/GetGraphdatatesttest'
    headers = {
        'Referer': 'https://www.worldcoinindex.com/coin/dogecoin',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
    }
    payload = {
        'marketid': name,
        'days': days,
    }

    url = '{}/{}'.format(HOSTNAME, endpoint)
    response = requests.post(url, payload, headers=headers)
    response.raise_for_status()
    return json.loads(response.text)


def get_histories(cache=None):
    if cache:
        LOGGER.debug('Loading from cache')
        with open('histories.json', 'r') as file_handle:
            histories = json.loads(file_handle.read())
        LOGGER.debug('Loaded from cache')
        return histories

    pool = multiprocessing.Pool(100)
    return pool.map(get_history, get_coin_names())


def analyze(histories):
    earlier = {}  # Label to Volume Market Cap Rank
    now = None
    lru_cache = {}  # Mapping of coin name to the last event we saw it in
    adder_cache = {}  # Mapping of coin name to the number of times seen

    for event_cluster in as_event_stream(histories):
        # Generate the updated view of the world of our coins
        now = dict(earlier)
        for event in event_cluster['Events']:
            now[event['primaryname']] = event['Volume'] * event['Price']

        # Print current timestamp for debugging and scale
        timestamp = event_cluster['Timestamp']
        readable_time = datetime.datetime.utcfromtimestamp(timestamp)
        LOGGER.debug('Timestamp: %s', readable_time)

        # Ignore early seed data where all values are 0
        if all([value == 0 for value in now.values()]):
            continue

        top_now = sorted(
            now.items(),
            cmp=lambda a, b: int(a[1] - b[1]),
            reverse=True
        )[:20]

        # Degrade the adder cache because of time lapse
        for name in adder_cache:
            adder_cache[name] -= 1

        # Add new items to the adder cache or refersh if in the lru_cache
        for item in top_now:
            name = item[0]
            if name in lru_cache:
                lru_cache[name] = DELAY_FOR_EVICTION
            else:
                adder_cache[name] = adder_cache.get(name, 0) + 2

        to_add = set()
        for name in adder_cache:
            if adder_cache[name] >= DELAY_FOR_INVITATION:
                to_add.add(name)

        for name in to_add:
            lru_cache[name] = DELAY_FOR_EVICTION
            del adder_cache[name]
            LOGGER.debug('%s has entered the top listings', name)

        to_delete = set()
        for name in lru_cache:
            lru_cache[name] -= 1
            if lru_cache[name] < 0:
                LOGGER.debug('%s has dropped off the last 5 times', name)
                to_delete.add(name)

        if to_delete:
            LOGGER.debug('Now:\n%s', pprint.pformat(top_now))
            LOGGER.debug('Last Few:\n%s', pprint.pformat(lru_cache))

        for name in to_delete:
            del lru_cache[name]

        earlier = dict(now)


def as_event_stream(histories):
    indexes = {}
    while True:
        # Get the next earliest timestamp
        min_timestamp = time.time()
        for history in histories:
            index = indexes.get(history['primaryname'], 0)
            if index >= len(history['data']):
                continue  # ? This might need to be a delete
            event = history['data'][index]
            if event['Timestamp'] < min_timestamp:
                min_timestamp = event['Timestamp']

        # Get every update at this time
        events = []
        for history in histories:
            index = indexes.get(history['primaryname'], 0)
            if index >= len(history['data']):
                continue  # ? This might need to be a delete
            event = history['data'][index]
            event['primaryname'] = history['primaryname']
            event['label'] = history['label']
            if event['Timestamp'] == min_timestamp:
                indexes[history['primaryname']] = index + 1
                events.append(event)

        yield {
            'Timestamp': min_timestamp,
            'Events': events
        }


def main():
    '''
    main
    '''
    configure_logging()
    histories = get_histories()
    import pdb
    pdb.set_trace()
    analyze(histories)


if __name__ == '__main__':
    main()
