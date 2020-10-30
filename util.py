''' Helper functions that are not necessarily related to server-side code '''

import datetime
import pandas as pd
import json

UTC_MARKET_OPEN = '13:30:00'
UTC_MARKET_CLOSE = '20:00:00'

# returns current date string in YYYY-MM-DD format
def get_current_date():
    return datetime.datetime.today().strftime('%Y-%m-%d')

# returns date n days ago from today in YYYY-MM-DD format
def get_date_n_days_ago(n):
    current_date = datetime.datetime.now()
    delta = datetime.timedelta(**{'days': n})
    n_days_ago = current_date - delta
    return n_days_ago.strftime('%Y-%m-%d')

# returns YYYY-MM-DD date format from epoch time
def epoch_to_date_format(epoch_time):
    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(epoch_time)/1000).strftime('%Y-%m-%d')
    return db_timestamp_format

# returns YYYY-MM-DD HH-MM-SS timestamp format from epoch time
def epoch_to_timestamp_format(epoch_time):
    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(epoch_time)/1000).strftime('%Y-%m-%d %H:%M:%S')
    return db_timestamp_format

# returns whether given epoch timestamp is within trading hours
def within_trading_hours(epoch_time):
    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(epoch_time)/1000).strftime('%H:%M:%S')
    return db_timestamp_format >= UTC_MARKET_OPEN and db_timestamp_format <= UTC_MARKET_CLOSE 

# reads csv file and returns list of tickers
def read_spy_tickers():
    df = pd.read_csv('spy500.csv')
    tickers = df['Symbol'].tolist()
    return tickers

# helper function for get request multithreading
def polygon_get_request_multithreaded(url, session):
    resp = session.get(url)
    if resp.ok:
        return json.loads(resp.text)
    return None