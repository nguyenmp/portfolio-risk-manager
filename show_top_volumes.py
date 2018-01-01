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


class TrackerEngine(object):
    '''
    This class wraps the concept of tracking what to add and what to remove
    based on a sliding window of what we've previously seen with the top
    market leaders
    '''

    DELAY_FOR_INVITATION = 10*5
    DELAY_FOR_EVICTION = 7*5

    lru_cache = {}  # Mapping of coin name to the last event we saw it in
    adder_cache = {}  # Mapping of coin name to the number of times seen

    def update(self, top_now, timestamp):
        '''
        Given a new ticker time, update our sliding window of what we should
        add and remove and return those as adds and removes from our index
        '''
        # Print current timestamp for debugging and scale
        readable_time = datetime.datetime.utcfromtimestamp(timestamp)
        LOGGER.debug('Updating for timestamp: %s', readable_time)

        # Degrade the adder cache because of time lapse
        for name in self.adder_cache:
            self.adder_cache[name] -= 1

        # Add new items to the adder cache or refersh if in the lru_cache
        for item in top_now:
            name = item[0]
            if name in self.lru_cache:
                self.lru_cache[name] = self.DELAY_FOR_EVICTION
            else:
                self.adder_cache[name] = self.adder_cache.get(name, 0) + 2

        to_add = set()
        for name in self.adder_cache:
            if self.adder_cache[name] >= self.DELAY_FOR_INVITATION:
                to_add.add(name)

        for name in to_add:
            self.lru_cache[name] = self.DELAY_FOR_EVICTION
            del self.adder_cache[name]
            LOGGER.debug('%s has entered the top listings', name)

        to_delete = set()
        for name in self.lru_cache:
            self.lru_cache[name] -= 1
            if self.lru_cache[name] < 0:
                LOGGER.debug('%s has dropped off the last 5 times', name)
                to_delete.add(name)

        for name in to_delete:
            del self.lru_cache[name]

        return to_add, to_delete


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


def get_history(name, days=90):
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


def get_histories(cache='tmp_cache.json'):
    if cache:
        LOGGER.debug('Loading from cache')
        with open('histories.json', 'r') as file_handle:
            histories = json.loads(file_handle.read())
        LOGGER.debug('Loaded from cache')
        return histories

    pool = multiprocessing.Pool(100)
    result = pool.map(get_history, get_coin_names())
    with open('tmp_cache.json', 'w') as file_handle:
        file_handle.write(json.dumps(result))
    return result


def update_ticker_view(earlier, events):
    '''
    Given previous knowledge of what stock tickers were like, and an update on
    what some of the stock tickers look like now , generate the new view on
    what they are
    '''
    now = dict(earlier)
    for event in events:
        now[event['primaryname']] = event['Volume'] * event['Price']
    return now


def get_top_by_volume(now, limit=20):
    '''
    Given a mapping of lavels to volume as market
    cap, returns the top `n` tickers
    '''
    return sorted(
        now.items(),
        cmp=lambda a, b: int(a[1] - b[1]),
        reverse=True
    )[:limit]


def analyze(histories):
    earlier = {}  # Label to Volume Market Cap
    tracker = TrackerEngine()

    for event_cluster in as_event_stream(histories):
        # Generate the updated view of the world of our coins
        now = update_ticker_view(earlier, event_cluster['Events'])

        # Get the top 20 coins sorted by volume measured as market cap
        top_now = get_top_by_volume(now)

        # Create a lookup table by name so we know wht we're buying and selling at
        events_by_name = {
            event['primaryname']: event
            for event in event_cluster['Events']
        }

        to_buy, to_sell = tracker.update(top_now, event_cluster['Timestamp'])
        for buy in to_buy:
            LOGGER.warning('Buying %s at %s', buy, events_by_name[buy]['Price'])
        for sell in to_sell:
            LOGGER.warning('Selling %s at %s', sell, events_by_name[sell]['Price'])

        earlier = dict(now)


def as_event_stream(histories):
    '''
    Converts the list of histories for each stock ticker
    into a stream of ticker updates grouped by time
    '''
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

        # Ignore early seed data where all values are 0
        if all([event['Volume'] == 0 for event in events]):
            continue

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
    analyze(histories)


if __name__ == '__main__':
    main()
