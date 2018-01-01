'''
This little script downloads the market price and volume traded day to day to
show how the top coins change over time.  The intention is to analyze how this
measure behaves given historical data.
'''

import logging
import sys

import sources
import processing


LOGGER = logging.getLogger()


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


def main():
    '''
    main
    '''
    configure_logging()
    histories = sources.get_histories()
    processing.analyze(histories)


if __name__ == '__main__':
    main()
