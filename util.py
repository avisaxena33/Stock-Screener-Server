''' Helper functions for endpoints '''

import json
import csv
import os
import datetime
import pandas as pd
import tweepy
import psycopg2
import re
import smtplib
import numpy
from statistics import mean, pstdev

from config import *
import logging.handlers

# Attempts to connect to database and returns connection object if successsful
def connect_to_postgres(): 
    try:
        return psycopg2.connect(host=DB_ENDPOINT, port=PORT, dbname=DB_NAME, user=MASTER_USERNAME, password=MASTER_PASSWORD)
    except Exception as e:
        print("Database connection failed due to {}".format(e))

# returns index of ema_vol array given ms epoch timestamp from polygon websocket
def get_ema_idx(ms_epoch_ts):
    ts = epoch_to_time_format(ms_epoch_ts)
    FMT = '%H:%M:%S'
    
    conv_ts = datetime.datetime.strptime(ts, FMT)
    conv_mkt_open = datetime.datetime.strptime(UTC_MARKET_OPEN, FMT)
    time_diff = conv_ts - conv_mkt_open
    time_diff_mins = (time_diff.seconds//60)
    return time_diff_mins

# Returns list of market holidays
def get_market_holidays(session):
    url = 'https://api.polygon.io/v1/marketstatus/upcoming?apiKey={}'.format(POLYGON_API_KEY)
    resp = polygon_get_request_multithreaded(url, session)
    if not resp:
        return []
    market_holidays = {day['date'] for day in resp if day['status'] == 'closed'}
    return market_holidays

# checks if given date is a market holiday
def is_market_holiday(curr_date, session):
    market_holidays = get_market_holidays(session)
    if not market_holidays or curr_date not in market_holidays:
        return False
    return True

# convert news api org timestamp to datetime
def news_api_timestamp_to_date(article_date):
    return datetime.datetime.strptime(article_date, "%Y-%m-%dT%H:%M:%SZ")

# convert date to datetime
def d2dt(d):
    return datetime.datetime.combine(d, datetime.time())

# returns stripped tweepy created_at date
def tweepy_date_to_datetime(tweet_date):
    return datetime.datetime.strftime(datetime.datetime.strptime(tweet_date,'%a %b %d %H:%M:%S +0000 %Y'), '%Y-%m-%d %H:%M:%S')

# returns current date string in YYYY-MM-DD format (UTC -> CST)
def get_current_date():
    return (datetime.datetime.utcnow()-datetime.timedelta(hours=6)).strftime('%Y-%m-%d')

# returns current day of week (0 = monday and 6 = sunday) (UTC -> CST)
def get_current_day_of_week():
    return (datetime.datetime.utcnow()-datetime.timedelta(hours=6)).weekday()

# returns date n days ago from given date (default to today) in YYYY-MM-DD format (UTC -> CST)
def get_date_n_days_ago(n, given_date=None):
    if not given_date:
        given_date = datetime.datetime.utcnow()-datetime.timedelta(hours=6)
    else:
        given_date = datetime.datetime.strptime(given_date, "%Y-%m-%d")
    delta = datetime.timedelta(**{'days': n})
    n_days_ago = given_date - delta
    return n_days_ago.strftime('%Y-%m-%d')

# returns datetime object n days ago from today (UTC -> CST)
def get_date_n_days_ago_datetime(n):
    current_date = datetime.datetime.utcnow()-datetime.timedelta(hours=6)
    delta = datetime.timedelta(**{'days': n})
    n_days_ago = current_date - delta
    return n_days_ago

# returns YYYY-MM-DD HH-MM-SS timestamp format from ms epoch time
def epoch_to_timestamp_format(epoch_time):
    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(epoch_time)/1000).strftime('%Y-%m-%d %H:%M:%S')
    return db_timestamp_format

# returns HH-MM-SS timestamp format from ms epoch time
def epoch_to_time_format(epoch_time):
    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(epoch_time)/1000).strftime('%H:%M:%S')
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

# AF1
# returns postfix form of custom user query for AF1
# if error in query syntax, returns None
def user_query_to_postfix(query):
    # replace query with operators
    rep_dict = {
        'std': 's',
        'mean': 'a',
        'and': '&',
        'or': '|',
        '[': '',
        ']': '',
        '(': ' ( ',
        ')': ' ) '
    }
    rep_keys = map(re.escape, rep_dict.keys())
    pattern = re.compile('|'.join(rep_keys))
    norm_query = pattern.sub(lambda m: rep_dict[m.group(0)], query)

    # query to postfix
    return infix_to_postfix(norm_query.split())

# AF1
# converts infix to postfix expression 
def infix_to_postfix(infix):
    def is_num(n):
        try:
            float(n)
            return True
        except ValueError:
            return False

    ret = list()
    s = list()
    operands = {'o','h','l','c','v','mo','mh','ml','mc','mv'}
    operators = {
        '|': 0,
        '&': 1,
        '<': 2,
        '>': 2,
        '<=': 2,
        '>=': 2,
        '==': 2,
        '+': 3,
        '-': 3,
        '*': 4,
        '/': 4,
        's': 5,
        'a': 5
    }
    for i in infix:
        # operand
        if is_num(i) or any(i[:j] in operands for j in range(1,3)):
            ret.append(i)
        elif i == '(':
            s.append(i)
        elif i == ')': 
            while s and s[-1] != '(': 
                a = s[-1]
                s.pop()
                ret.append(a) 
            if not s:
                return None
            else: 
                s.pop() 
        # operator
        elif i in operators: 
            while s and s[-1] != '(' and operators[i] <= operators[s[-1]]: 
                ret.append(s[-1])
                s.pop()
            s.append(i)
        # invalid syntax
        else:
            return None
    ret.extend(s[::-1])
    
    return ' '.join(ret)

# AF1
# evaluates a user postfix query given two arrays of price data
# True: 1, False: 0, Error: -1
def evaluate_user_query(query, day, minute):
    s = list()
    operators = {'|','&','<','>','<=','>=','==','+','-','*','/','s','a'}
    d = {'o':2, 'c':3, 'h':4, 'l':5, 'v':6}
    # logger.info('test')
    for q in query.split():
        # operand
        if q not in operators:
            if q[0] == 'm':
                if len(q) == 2:
                    s.append(q)
                    continue
                pos = int(q[2:])
                val = d[q[1]]
                s.append(minute[pos][val])
            elif q[0] in d:
                if len(q) == 1:
                    s.append(q)
                    continue
                pos = int(q[1:])
                val = d[q[0]]
                s.append(day[pos][val])
            else:
                s.append(float(q))
        # operator
        else:
            b = s[-1]
            s.pop()
            a = s[-1]
            s.pop()
            if q == '|':
                s.append(1 if a or b else 0)
            elif q == '&':
                s.append(1 if a and b else 0)
            elif q == '<':
                s.append(1 if a < b else 0)
            elif q == '>':
                s.append(1 if a > b else 0)
            elif q == '<=':
                s.append(1 if a <= b else 0)
            elif q == '>=':
                s.append(1 if a >= b else 0)
            elif q == '==':
                s.append(1 if a == b else 0)
            elif q == '+':
                s.append(a + b)
            elif q == '-':
                s.append(a - b)
            elif q == '*':
                s.append(a * b)
            elif q == '/':
                s.append(a / b)
            elif q == 's' or q == 'a':
                x = s[-1]
                s.pop()
                a = int(a)
                b = int(b)

                def func(y):
                    if q == 's':
                        return pstdev(i[d[x[-1]]] for i in y)
                    else:
                        return mean(i[d[x[-1]]] for i in y)

                if x[0] == 'm' and minute:
                    s.append(func(minute[b:b+a]))
                else:
                    s.append(func(day[b:b+a]))
            else:
                return -1
    
    if len(s) != 1:
        return -1
    return 1 if s[0] else 0        

# adds daily price data (for last 365 days) for a newly tracked ticker
def add_daily_price_data(ticker, session, connection, cursor):
    url = '{}/v2/aggs/ticker/{}/range/1/day/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(365), get_current_date(), POLYGON_API_KEY) 
    resp = polygon_get_request_multithreaded(url, session)

    if not resp or len(resp['results']) == 0:
        LOGGER.info('NO RESPONSE FROM POLYGON ON ADD_TRACKER')
        return None

    most_recent_day_data = None
    most_recent_timestamp = None
    with open ('new_daily_price_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        curr_ticker = resp['ticker']
        for day in resp['results']:
            db_timestamp_format = epoch_to_timestamp_format(day['t'])
            if not most_recent_timestamp or db_timestamp_format > most_recent_timestamp:
                most_recent_day_data = day
                most_recent_timestamp = db_timestamp_format
            prices = [curr_ticker, db_timestamp_format, day['o'], day['c'], day['h'], day['l'], day['v']]
            write.writerow(prices)
    csv_file = open('new_daily_price_data.csv', 'r')
    try:
        cursor.copy_expert("copy Daily_Prices from stdin (format csv)", csv_file)
    except Exception as e:
        print({'error': e})
        LOGGER.info('FAILED TO COPY FROM CSV ON ADD_TRACKER')
        csv_file.close()
        os.remove('new_daily_price_data.csv')
        return None

    csv_file.close()
    os.remove('new_daily_price_data.csv')

    recent_open = most_recent_day_data['o']
    recent_close = most_recent_day_data['c']
    recent_percent_change = (recent_close / recent_open - 1)*100

    try:
        cursor.execute("CALL update_tracker_price_data(%s, %s, %s, %s, %s)", (ticker, recent_open, recent_close, recent_percent_change, most_recent_timestamp,))
    except Exception as e:
        LOGGER.info('FAILED TO UPDATE TRACKER PRICE DATA')
        return None
    return 'SUCCESSFULLY ADDED DAILY PRICE DATA FOR {}'.format(ticker)

# adds current day's closing price data for a ticker (used by cron job endpoint)
def add_daily_closing_price(ticker, session):
    url = '{}/v2/aggs/ticker/{}/prev?apiKey={}'.format(POLYGON_BASE_URL, ticker, POLYGON_API_KEY) 
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    
    resp = resp['results'][0]
    timestamp = epoch_to_timestamp_format(resp['t'])

    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Daily_Prices (ticker, timestamp, open, close, high, low, volume) VALUES(%s, %s, %s, %s, %s, %s, %s)", (ticker, timestamp, resp['o'], resp['c'], resp['h'], resp['l'], resp['v'],))
    except Exception as e:
        print({'error': e})
        cursor.close()
        connection.close()
        return None

    connection.commit()
    recent_percent_change = (resp['c'] / resp['o'] - 1)*100
    try:
        cursor.execute("CALL update_tracker_price_data(%s, %s, %s, %s, %s)", (ticker, resp['o'], resp['c'], recent_percent_change, timestamp,))
    except Exception as e:
        cursor.close()
        connection.close()
        return None

    connection.commit()
    cursor.close()
    connection.close()
    return 'SUCCESSFULLY ADDED CLOSING PRICE DATA TODAY FOR {}'.format(ticker)

# adds minute-by-minute price data (for the last trading day) for a newly tracked ticker
def add_minute_price_data(ticker, session, connection, cursor):
    url = None
    curr_day_of_week = get_current_day_of_week()
    initial_date_pulled = None
    if curr_day_of_week == 0:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(3), get_date_n_days_ago(3), POLYGON_API_KEY)
        initial_date_pulled = get_date_n_days_ago(3)
    elif curr_day_of_week == 6:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(2), get_date_n_days_ago(2), POLYGON_API_KEY)
        initial_date_pulled = get_date_n_days_ago(2)
    else:
        url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(1), get_date_n_days_ago(1), POLYGON_API_KEY)
        initial_date_pulled = get_date_n_days_ago(1)
    
    resp = polygon_get_request_multithreaded(url, session)
    # in case some day is bugged, let's try up to 10 previous days before the pulled date (should also take care of market holidays)
    if not resp or len(resp['results']) == 0:
        try_days = 1
        while try_days < 11:
            try_days += 1
            url = '{}/v2/aggs/ticker/{}/range/1/minute/{}/{}?sort=asc&apiKey={}'.format(POLYGON_BASE_URL, ticker, get_date_n_days_ago(1, initial_date_pulled), get_date_n_days_ago(1, initial_date_pulled), POLYGON_API_KEY)
            resp = polygon_get_request_multithreaded(url, session)
            if resp and len(resp['results']) > 0:
                break     

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
    try:
        cursor.copy_expert("copy Minute_Prices from stdin (format csv)", csv_file)
    except Exception as e:
        LOGGER.info(e)
        csv_file.close()
        os.remove('new_minute_price_data.csv')
        return None
    
    csv_file.close()
    os.remove('new_minute_price_data.csv')
    return 'SUCCESSFULLY ADDED MINUTE PRICE DATA FOR {}'.format(ticker)

# adds minute-by-minute price data for the current day (cron job)
def add_daily_minute_price(ticker, session):
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
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.copy_expert("copy Minute_Prices from stdin (format csv)", csv_file)
    except Exception as e:
        print({'error': e})
        csv_file.close()
        cursor.close()
        connection.close()
        os.remove('new_minute_price_data.csv')
        return None

    csv_file.close()
    connection.commit()
    cursor.close()
    connection.close()
    os.remove('new_minute_price_data.csv')
    return 'SUCCESSFULLY ADDED MINUTE PRICE DATA FOR {}'.format(ticker)

# adds tweets for a newly tracked ticker
def add_tweets(ticker, company_name, tweepy_api, session, connection, cursor):
    query = company_name
    max_tweets = 50
    searched_tweets = [status._json for status in tweepy.Cursor(tweepy_api.search, q=query, lang='en').items(max_tweets)]
    
    with open('new_tweets_data.csv', 'w+', newline='') as csv_file:
        write = csv.writer(csv_file)
        for tweet in searched_tweets:
            tweet = [TWEET_BASE_URL+tweet['id_str'], tweet['text'].encode('utf-8'), ticker, tweepy_date_to_datetime(tweet['created_at'])]
            write.writerow(tweet)
    csv_file = open('new_tweets_data.csv', 'r')
    try:
        cursor.copy_expert("copy Tweets from stdin (format csv)", csv_file)
    except Exception as e:
        LOGGER.info(e)
        csv_file.close()
        os.remove('new_tweets_data.csv')
        return None
    csv_file.close()
    os.remove('new_tweets_data.csv')
    return 'SUCCESSFULLY ADDED TWEETS DATA FOR {}'.format(ticker)

# adds news articles for a newly tracked ticker
def add_news_articles(ticker, session, connection, cursor):
    url = 'https://newsapi.org/v2/everything?language=en&q={}&pageSize=50&page=1&apiKey={}'.format(ticker, NEWS_API_KEY)
    resp = polygon_get_request_multithreaded(url, session)
    if not resp:
        return None

    # must do this because for whatever reason the search can return duplicate articles
    articles_url_seen = set()
    unique_articles = []
    for article in resp['articles']:
        if article['url'] not in articles_url_seen:
            articles_url_seen.add(article['url'])
            unique_articles.append(article)

    with open('new_news_data.csv', 'w+', encoding="utf-8", newline='') as csv_file:
        write = csv.writer(csv_file)
        for article in unique_articles:
            if not article['description'] or len(article['description']) == 0:
                article['description'] = 'No Description Available'
            if not article['title'] or len(article['title']) == 0:
                article['title'] = 'No Title Available'
            prices = [news_api_timestamp_to_date(article['publishedAt']), ticker, article['title'].encode('utf-8'), article['url'], article['description'].encode('utf-8')]
            write.writerow(prices)
    csv_file = open('new_news_data.csv', 'r')
    try:
        cursor.copy_expert("copy News from stdin (format csv)", csv_file)
    except Exception as e:
        csv_file.close()
        os.remove('new_news_data.csv')
        return None
    csv_file.close()
    os.remove('new_news_data.csv')
    return 'SUCCESSFULLY ADDED NEWS DATA FOR {}'.format(ticker)

# function that grabs daily prices for past week of a ticker to add to mongodb array
def get_past_week_prices_mongo(ticker, session):
    week_ago = get_date_n_days_ago(7)
    today = get_current_date()
    url = 'https://api.polygon.io/v2/aggs/ticker/{}/range/1/day/{}/{}?sort=asc&apiKey={}'.format(ticker, week_ago, today, POLYGON_API_KEY)
    resp = polygon_get_request_multithreaded(url, session)
    if not resp or len(resp['results']) == 0:
        return None
    resp = resp['results']

    daily_prices = []
    for day in resp:
        new_timestamp = datetime.datetime.strptime(epoch_to_timestamp_format(day['t']), '%Y-%m-%d %H:%M:%S')
        new_day = {'volume': day['v'], 'open': day['o'], 'close': day['c'], 'high': day['h'], 'low': day['l'], 'timestamp': new_timestamp}
        daily_prices.append(new_day)

    return daily_prices

# Send an email via Gmail SMTP (used for EMA Volume spikes and custom queries)    
def send_volume_spike_notification(message):
    to = [GMAIL_USER_1, GMAIL_USER_2, GMAIL_USER_3]
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(GMAIL_ROOT_USER, GMAIL_ROOT_PASS)
        server.sendmail(GMAIL_ROOT_USER, to, message)
        server.close()
        LOGGER.info('Email sent!')
    except:
        LOGGER.error('Something went wrong...')
    
