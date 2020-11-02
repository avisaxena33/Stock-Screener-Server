''' Helper functions for endpoints '''

import json
import csv
import os
import datetime
import pandas as pd
import tweepy

from config import *

UTC_MARKET_OPEN = '13:30:00'
UTC_MARKET_CLOSE = '20:00:00'
TWEET_BASE_URL = 'https://twitter.com/user/status/'

# convert date to datetime
def d2dt(d):
    return datetime.datetime.combine(d, datetime.time())

# returns stripped tweepy created_at date
def tweepy_date_to_datetime(tweet_date):
    return datetime.datetime.strftime(datetime.datetime.strptime(tweet_date,'%a %b %d %H:%M:%S +0000 %Y'), '%Y-%m-%d %H:%M:%S')

# returns current date string in YYYY-MM-DD format
def get_current_date():
    return datetime.datetime.today().strftime('%Y-%m-%d')

def get_current_date_datetime():
    return datetime.datetime.today()

# returns current day of week (0 = monday and 6 = sunday)
def get_current_day_of_week():
    return datetime.datetime.today().weekday()

# returns date n days ago from today in YYYY-MM-DD format
def get_date_n_days_ago(n):
    current_date = datetime.datetime.now()
    delta = datetime.timedelta(**{'days': n})
    n_days_ago = current_date - delta
    return n_days_ago.strftime('%Y-%m-%d')

def get_date_n_days_ago_datetime(n):
    current_date = datetime.datetime.now()
    delta = datetime.timedelta(**{'days': n})
    n_days_ago = current_date - delta
    return n_days_ago

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

# adds daily price data (for last 365 days) for a newly tracked ticker
def add_daily_price_data(ticker, session, connection, cursor):
    url = '{}/v2/aggs/ticker/{}/range/1/day/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(365), get_current_date(), POLYGON_API_KEY) 
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    with open ('new_daily_price_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        curr_ticker = resp['ticker']
        for day in resp['results']:
            db_timestamp_format = epoch_to_timestamp_format(day['t'])
            prices = [curr_ticker, db_timestamp_format, day['o'], day['c'], day['h'], day['l'], day['v']]
            write.writerow(prices)
    csv_file = open('new_daily_price_data.csv', 'r')
    cursor.copy_from(csv_file, 'Daily_Prices', sep=',', columns=('ticker', 'timestamp', 'open', 'close', 'high', 'low', 'volume'))
    csv_file.close()
    os.remove('new_daily_price_data.csv')
    return 'SUCCESSFULLY ADDED DAILY PRICE DATA FOR {}'.format(ticker)

# adds minute-by-minute price data (for the last trading day) for a newly tracked ticker
def add_minute_price_data(ticker, session, connection, cursor):
    url = None
    curr_day_of_week = get_current_day_of_week()
    if curr_day_of_week == 0:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(3), get_date_n_days_ago(3), POLYGON_API_KEY)
    elif curr_day_of_week == 6:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(2), get_date_n_days_ago(2), POLYGON_API_KEY)
    else:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(1), get_date_n_days_ago(1), POLYGON_API_KEY)
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    
    with open('new_minute_price_data.csv', 'w+', newline='') as csv_file:
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
    return 'SUCCESSFULLY ADDED MINUTE PRICE DATA FOR {}'.format(ticker)

# adds tweets for a newly tracked ticker
def add_tweets(ticker, tweepy_api, session, connection, cursor):
    query = ticker
    max_tweets = 50
    searched_tweets = [status._json for status in tweepy.Cursor(tweepy_api.search, q=query).items(max_tweets)]
    
    with open('new_tweets_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        for tweet in searched_tweets:
            tweet = [tweet['id_str'], tweet['text'].encode('utf-8'), ticker, tweepy_date_to_datetime(tweet['created_at'])]
            print(tweet[0])
            write.writerow(tweet)
    csv_file = open('new_tweets_data.csv', 'r')
    cursor.copy_expert("copy Tweets from stdin (format csv)", csv_file)
    csv_file.close()
    os.remove('new_tweets_data.csv')
    return 'SUCCESSFULLY ADDED TWEETS DATA FOR {}'.format(ticker)

# adds news articles for a newly tracked ticker
def add_news_articles(ticker, session, connection, cursor):
    url = '{}/v1/meta/symbols/{}/news?perpage=50&page=1&apiKey={}'.format(POLYGON_BASE_URL, ticker, POLYGON_API_KEY)
    resp = polygon_get_request_multithreaded(url, session)
    
    with open('new_news_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        for article in resp:
            prices = [article['timestamp'], ticker, article['title'], article['url'], article['summary']]
            write.writerow(prices)
    csv_file = open('new_news_data.csv', 'r')
    cursor.copy_expert("copy News from stdin (format csv)", csv_file)
    # cursor.copy_from(csv_file, 'News', sep=',', columns=('timestamp', 'ticker', 'title', 'url', 'summary'))
    csv_file.close()
    os.remove('new_news_data.csv')
    return 'SUCCESSFULLY ADDED NEWS DATA FOR {}'.format(ticker)
    
