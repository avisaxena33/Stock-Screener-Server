''' Helper functions for endpoints '''

import json
import csv
import os
import datetime
import pandas as pd

UTC_MARKET_OPEN = '13:30:00'
UTC_MARKET_CLOSE = '20:00:00'

# returns current date string in YYYY-MM-DD format
def get_current_date():
    return datetime.datetime.today().strftime('%Y-%m-%d')

# returns current day of week (0 = monday and 6 = sunday)
def get_current_day_of_week():
    return datetime.datetime.today().weekday()

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

def add_daily_price_data(ticker, session, connection, cursor):
    url = 'https://api.polygon.io/v2/aggs/ticker/' + ticker + '/range/1/day/' + get_date_n_days_ago(365) + '/' + get_current_date() + '?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    with open ('new_daily_price_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        curr_ticker = resp['ticker']
        for day in resp['results']:
            db_date_format = epoch_to_date_format(day['t'])
            prices = [curr_ticker, db_date_format, day['o'], day['c'], day['h'], day['l'], day['v']]
            write.writerow(prices)
    csv_file = open('new_daily_price_data.csv', 'r')
    cursor.copy_from(csv_file, 'Daily_Prices', sep=',', columns=('ticker', 'date', 'open', 'close', 'high', 'low', 'volume'))
    csv_file.close()
    os.remove('new_daily_price_data.csv')
    return 'SUCCESSFULLY ADDED DAILY PRICE DATA FOR' + ' ' + ticker

def add_minute_price_data(ticker, session, connection, cursor):
    url = None
    curr_day_of_week = get_current_day_of_week()
    if curr_day_of_week == 0:
        url = 'https://api.polygon.io/v2/aggs/ticker/' + ticker + '/range/1/minute/' + get_date_n_days_ago(3) + '/' + get_date_n_days_ago(3) + '?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    elif curr_day_of_week == 6:
        url = 'https://api.polygon.io/v2/aggs/ticker/' + ticker + '/range/1/minute/' + get_date_n_days_ago(2) + '/' + get_date_n_days_ago(2) + '?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    else:
        url = 'https://api.polygon.io/v2/aggs/ticker/' + ticker + '/range/1/minute/' + get_date_n_days_ago(1) + '/' + get_date_n_days_ago(1) + '?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    count = 0
    with open ('new_minute_price_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        curr_ticker = resp['ticker']
        for minute in resp['results']:
            if within_trading_hours(minute['t']):
                db_timestamp_format = epoch_to_timestamp_format(minute['t'])
                prices = [curr_ticker, db_timestamp_format, minute['o'], minute['c'], minute['h'], minute['l'], minute['v']]
                write.writerow(prices)
    csv_file = open('new_minute_price_data.csv', 'r')
    cursor.copy_from(csv_file, 'Minute_Prices', sep=',', columns=('ticker', 'timestamp', 'open', 'close', 'high', 'low', 'volume'))
    csv_file.close()
    os.remove('new_minute_price_data.csv')
    return 'SUCCESSFULLY ADDED MINUTE PRICE DATA FOR' + ' ' + ticker