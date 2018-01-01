'''
This module wraps around how we get our data to process
'''

import json
import logging
import multiprocessing
import re

import requests

API_KEY = '0BbG9UxZhOvmEHdfSHAOtUlAN3RoBd'
HOSTNAME = 'https://www.worldcoinindex.com'

LOGGER = logging.getLogger()


def get_histories(cache='tmp_cache.json'):
    '''
    Gets all historical data from all known crypto coins
    '''
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
