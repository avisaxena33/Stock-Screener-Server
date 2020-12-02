import sys
import boto3
import psycopg2
import pymongo
from flask import Flask
import util
import requests 
import time
import concurrent.futures
import threading
import json
import tweepy
import datetime
from pytz import utc
from flask_cors import CORS
import logging.handlers
import smtplib
import heapq

from config import *
import socket_bot

# Flask class reference (allow CORS on all domains)
application = app = Flask(__name__)
CORS(application)
session = requests.Session() 

# Start up the app and websocket daemon thread
LOGGER.info('About to run the flask app ...')
LOGGER.info('About to run the daemon thread ....')
t = threading.Thread(target=socket_bot.run_bot)
t.daemon = True
t.start()

# testing flask rest calls
@application.route("/")
def hello():
    LOGGER.info('YEET ROOT ROUTE')
    return 'CS 411 Stock Screener API'

'''
Tracks a new ticker if not already tracked and adds price data, news, and tweets
'''
@application.route('/add_tracker/<string:ticker>')
def add_tracker(ticker):
    ticker = ticker.upper()
    fundamentals = {}
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL add_tracker(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    if not util.add_daily_price_data(ticker, session, connection, cursor) or not util.add_minute_price_data(ticker, session, connection, cursor):
        cursor.close()
        connection.close()
        return {'error': 'COULD NOT ADD PRICE DATA FOR' + ' ' + ticker}
    util.add_tweets(ticker, TWEEPY_API, session, connection, cursor)
    util.add_news_articles(ticker, session, connection, cursor)
    try:
        cursor.execute("SELECT * FROM Fundamentals WHERE ticker = %s", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    fundamentals = cursor.fetchone()

    col_ref = mongo_db['Live_Stock_Prices']
    daily_prices = util.get_past_week_prices_mongo(ticker, session)
    if daily_prices:
        connection.commit()
        cursor.close()
        connection.close()
        new_tracker = {'ticker': ticker, 'name': fundamentals[1], 'industry': fundamentals[2], 'sector': fundamentals[3], 'market_cap': fundamentals[4], 'description': fundamentals[5], 'daily_prices': daily_prices, 'minute_prices': [], 'prev_ema': [-1]*391, 'ema_volume': [-1]*391, 'minute_volume': [-1]*391}
        col_ref.insert_one(new_tracker)
    else:
        cursor.close()
        connection.close()
        return {'error': 'Failed to add {}!'.format(ticker)}

    return {'success': 'Successfully added {}!'.format(ticker)}

'''
Removes a ticker that is being tracked alongside all the price, tweets, and news data for that ticker
'''
@application.route('/remove_tracker/<string:ticker>')
def remove_tracker(ticker):
    ticker = ticker.upper()
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_tracker(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    connection.commit()
    cursor.close()
    connection.close()

    col_ref = mongo_db['Live_Stock_Prices']
    col_ref.delete_one({'ticker': ticker })
    return {'success': 'Successfully removed {}!'.format(ticker)}

'''
Removes all tickers that are being tracked (BESIDES SPY) alongside all the price, tweets, and news data for that ticker 
'''
@application.route('/remove_all_trackers')
def remove_all_trackers():
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_all_trackers();")
    except Exception as e:
        return {'error': str(e)}
    connection.commit()
    cursor.close()
    connection.close()

    col_ref = mongo_db['Live_Stock_Prices']
    col_ref.delete_many({ 'ticker': { '$ne': 'SPY' }, 'usecase': {'$ne': 'af2' } })
    return {'success': 'Successfully removed all trackers!'}

'''
Replaces old tweets with new tweets for a given ticker
'''
@application.route('/update_tweets/<string:ticker>')
def update_tweets(ticker):
    ticker = ticker.upper()
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_tweets(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    util.add_tweets(ticker, TWEEPY_API, session, connection, cursor)
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': 'Successfully updated news for {}!'.format(ticker)}  

'''
Removes all news data for a given ticker
'''
@application.route('/update_news/<string:ticker>')
def update_news(ticker):
    ticker = ticker.upper()
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_news(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    util.add_news_articles(ticker, session, connection, cursor)
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': 'Successfully updated news for {}!'.format(ticker)}

'''
Update notes for a given tracked ticker (now supports default arg for notes -- when notes is empty)
'''
@application.route('/update_notes/<string:ticker>/', defaults={'notes': ''})
@application.route('/update_notes/<string:ticker>/<string:notes>')
def update_notes(ticker, notes):
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute(
            '''
            UPDATE Trackers
            SET notes = %s
            WHERE ticker = %s
            '''
            ,
            (notes, ticker)
        )
    except Exception as e:
        return {'error': str(e)}
    
    connection.commit()
    cursor.close()
    connection.close()

    return {'success': 'Successfully updated note for {}!'.format(ticker)}

'''
Returns a list of all available tickers to track

Returns:
{
    'tickers': [
        'AAPL'
    ]
}
'''
@application.route('/get_all_tickers')
def get_all_tickers():
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ticker FROM Fundamentals")
    except Exception as e:
        return {'error': str(e)}
    tickers = [record[0] for record in cursor]
    connection.commit()
    cursor.close()
    connection.close()
    return {'tickers': tickers}

'''
Grabs all currently tracked stocks most recent price data

Returns: 
{
    'tracked': [
        {
            'ticker': AAPL, 
            'close': 123.00, 
            'percentage_change': -1.34
        }
    ]
}
'''
@application.route('/get_trackers')
def get_trackers():
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ticker, open, close, percent_change, notes, timestamp FROM Trackers")
    except Exception as e:
        return {'error': str(e)}
    tracked_raw_data = [record for record in cursor]
    if not tracked_raw_data or len(tracked_raw_data) == 0:
        return {'error': 'No stocks are currently being tracked'}
    tracked_stocks = []
    for stock in tracked_raw_data:
        temp = {
            'ticker': stock[0], 
            'open': stock[1],
            'close': stock[2], 
            'percentage_change': stock[3],
            'notes': stock[4],
            'timestamp': stock[5]
        }
        tracked_stocks.append(temp)
    cursor.close()
    connection.close()
    return {'tracked': tracked_stocks}

'''
gets all data for a specified ticker page

Returns:
{
    'ticker': 'AAPL',
    'prices': {
        '1d': [
            {
                'timestamp': 123,
                'open': 123,
                'close': 123,
                'high': 123,
                'low': 123
            }, ...
        ],
        '5d': [...],
        '1m': [...],
        '3m': [...],
        '6m': [...],
        '1y': [...]
    },
    'fundamentals': {
        'volume': 123,
        'company_name': 123, 
        'industry': 123, 
        'sector': 123, 
        'market_cap': 123, 
        'description': 123
    },
    'news': [
        {
            'timestamp': 123, 
            'ticker': 123, 
            'title': 123, 
            'url': 123, 
            'summary': 123
        }
    ],
    'tweets': [
        {
            'url': 123, 
            'tweet': 123, 
            'ticker': 123, 
            'timestamp': 123,
        }
    ]
}
'''
@application.route('/get_data/<string:ticker>')
def get_ticker_data(ticker):
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    ticker = ticker.upper()
    add_tracker(ticker)
    try:
        cursor.execute(
            '''
            SELECT * 
            FROM Fundamentals 
            WHERE ticker = %s
            '''
            ,
            [ticker]
        )
    except Exception as e:
        return {'error': str(e)}

    fundamentals = cursor.fetchone()
    
    try:
        cursor.execute(
            '''
            SELECT *
            FROM Daily_Prices
            WHERE ticker = %s
            ORDER BY timestamp DESC
            '''
            ,
            [ticker]
        )
    except Exception as e:
        return {'error': str(e)}

    daily_prices = [record for record in cursor]

    try:
        cursor.execute(
            '''
            SELECT *
            FROM Minute_Prices
            WHERE ticker = %s
            ORDER BY timestamp DESC
            '''
            ,
            [ticker]
        )
    except Exception as e:
        return {'error': str(e)}

    minute_prices = [record for record in cursor]

    try:
        cursor.execute(
            '''
            SELECT *
            FROM News
            WHERE ticker = %s
            ORDER BY timestamp DESC
            LIMIT 5
            '''
            ,
            [ticker]
        )
    except Exception as e:
        return {'error': str(e)}

    news = [list(record) for record in cursor]
    for article in news:
        temp_title = article[2].encode('latin1').decode('unicode-escape').encode('latin1').decode('utf-8')
        temp_desc = article[4].encode('latin1').decode('unicode-escape').encode('latin1').decode('utf-8')
        article[2] = temp_title[2:len(temp_title)-1]
        article[4] = temp_desc[2:len(temp_desc)-1]

    try:
        cursor.execute(
            '''
            SELECT *
            FROM Tweets
            WHERE ticker = %s
            ORDER BY timestamp DESC
            LIMIT 50
            '''
            ,
            [ticker]
        )
    except Exception as e:
        return {'error': str(e)}

    tweets = [list(record) for record in cursor]
    for tweet in tweets:
        temp = tweet[1].encode('latin1').decode('unicode-escape').encode('latin1').decode('utf-8')
        tweet[1] = temp[2:len(temp)-1]

    if not fundamentals:
        return {'error': 'No fundamental data found'}
    if not daily_prices:
        return {'error': 'No daily_prices data found'}
    if not minute_prices:
        return {'error': 'No minute_prices data found'}
    
    ticker_data = {
        'ticker': ticker,
        'prices': {
            '1d': list(),
            '5d': list(),
            '1m': list(),
            '3m': list(),
            '6m': list(),
            '1y': list()
        },
        'fundamentals': {
            'ticker': fundamentals[0],
            'company_name': fundamentals[1], 
            'industry': fundamentals[2], 
            'sector': fundamentals[3], 
            'market_cap': fundamentals[4], 
            'description': fundamentals[5]
        },
        'news': list(),
        'tweets': list()
    }

    for article in news:
        temp = {
            'timestamp': article[0], 
            'ticker': article[1], 
            'title': article[2], 
            'url': article[3], 
            'summary': article[4]
        }
        ticker_data['news'].append(temp)

    for tweet in tweets:
        temp = {
            'url': tweet[0], 
            'tweet': tweet[1], 
            'ticker': tweet[2], 
            'timestamp': tweet[3],
        }
        ticker_data['tweets'].append(temp)
    
    # datetime5d = util.get_date_n_days_ago_datetime(7)
    datetime1m = util.get_date_n_days_ago_datetime(31)
    datetime3m = util.get_date_n_days_ago_datetime(62)
    datetime6m = util.get_date_n_days_ago_datetime(183)

    for day in daily_prices:
        temp = {
            'timestamp': day[1],
            'open': day[2],
            'close': day[3],
            'high': day[4],
            'low': day[5]
        }
        if len(ticker_data['prices']['5d']) < 5:
            ticker_data['prices']['5d'].append(temp)
        if day[1] >= datetime1m:
            ticker_data['prices']['1m'].append(temp)
        if day[1] >= datetime3m:
            ticker_data['prices']['3m'].append(temp)
        if day[1] >= datetime6m:
            ticker_data['prices']['6m'].append(temp)
        ticker_data['prices']['1y'].append(temp)
    
    for minute in minute_prices:
        temp = {
            'timestamp': minute[1],
            'open': minute[2],
            'close': minute[3],
            'high': minute[4],
            'low': minute[5]
        }
        ticker_data['prices']['1d'].append(temp)
    
    for k, v in ticker_data['prices'].items():
        ticker_data['prices'][k] = v[::-1]

    cursor.close()
    connection.close()
    return ticker_data

'''
Gets the correlation coefficient of all stocks within a sector for each sector 
for a specific timeframe(day, minute).

Input:
timeframe - 'day' or 'minute'

Returns:
{
    'success': [
        {
            'sector': 'Tech',
            'correlation': float
        }
    ]
}
'''
@application.route('/get_correlations/<string:timeframe>')
def get_correlations(timeframe):
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM get_correlation(%s);", (timeframe,))
    except Exception as e:
        return {'error': str(e)}

    correlations = [{'sector': record[0], 'correlation': record[1]} for record in cursor]

    cursor.close()
    connection.close()
    return {'success': correlations}

'''
Gets the mean and std_dev percent change of all stocks within a market cap range for each 
market cap grade for a specific timeframe(day, minute).

Input:
timeframe - 'day' or 'minute'

Returns:
{
    'success': [
        {
            'grade': 3,
            'mean_percent_change': float
            'std_dev_percent_change': float
        }
    ]
}
'''
@application.route('/get_market_cap_grade_percent_change/<string:timeframe>')
def get_market_cap_grade_percent_change(timeframe):
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM get_percent_change(%s);", (timeframe,))
    except Exception as e:
        return {'error': str(e)}

    market_cap_percent_change = [{'grade': record[0], 'mean_percent_change': record[1], 'std_dev_percent_change': record[2]} for record in cursor]

    cursor.close()
    connection.close()
    return {'success': market_cap_percent_change}

'''
Returns:
{
    'success': [
        {
            'ema_diff': 1005.3434,
            'ticker': 'FB'
        }
    ]
}
'''
@application.route('/get_largest_emas')
def get_largest_emas():
    col_ref = mongo_db['Live_Stock_Prices']
    heap = []
    curr_ms_ts = time.time() * 1000
    idx = util.get_ema_idx(curr_ms_ts) - 1
    if idx < 0:
        idx = 0
    elif idx > 390:
        idx = 390
    for tracker in col_ref.find():
        if 'usecase' not in tracker:
            prev_ema = tracker['prev_ema'][idx]
            if prev_ema < 0:
                if len(tracker['daily_prices']) > 0:
                    prev_ema = tracker['daily_prices'][-1]['volume'] * idx / 390
                else:
                    prev_ema = tracker['ema_volume'][idx]
            val = tracker['ema_volume'][idx] / (prev_ema * MULTIPLIER) * 100
            heapq.heappush(heap, (val, tracker['ticker']))
        if len(heap) > 5:
            heapq.heappop(heap)
    
    top_five_emas = []
    while heap:
        curr_stock = heapq.heappop(heap)
        top_five_emas.append({'ema_diff': curr_stock[0], 'ticker': curr_stock[1]})

    return {'success': top_five_emas}

'''
Adds a custom user query to the database to execute on a daily basis

Input:
name - a name for the query
query - a string that represents a user query.
        specify on frontend:
        - must use python fromatting
        - arrays available are:
            (day candles)'o','h','l','c','v'
            (minute candles)'mo','mh','ml','mc','mv'
        - supported operators and predence (lowest precedence is 0):
        {
            'or': 0,
            'and': 1,
            '<': 2,
            '>': 2,
            '<=': 2,
            '>=': 2,
            '==': 2,
            '+': 3,
            '-': 3,
            '*': 4,
            '/': 4,
            'std': 5,
            'mean': 5
        }
        - for 'std' and 'mean' use this format:
            [data array] mean [period] [day]
            e.g. 'c mean 20 0' = 20-day closing price simple moving average on day 0 (most recent day)
            e.g. 'h std 12 5' = 12-day high price standard deviation on day 5 (5 days ago)
        - example query:
            c[0] > o[0] and c[1] < o[1] and c[0] > 0.5 * (c std 20 0) + (c mean 20 0)

Returns:
{
    'query': string - the user query,
    'postfix': string - postfix of query (if we ever need on frontend)
}
'''
@application.route('/add_custom_query/<string:name>/<string:query>')
def add_custom_query(name, query):
    postfix = util.user_query_to_postfix(query)
    if not postfix:
        return {'error': 'invalid syntax'}
    
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute(
            '''
            INSERT INTO Queries
                (name, query, postfix)
            VALUES
                (%s, %s, %s)
            ON CONFLICT (query)
            DO NOTHING
            '''
            ,
            [name, query, postfix]
        )
    except Exception as e:
        connection.rollback()
        return {'error': str(e)}
    connection.commit()

    cursor.close()
    connection.close()
    return {'name': name, 'query': query, 'postfix': postfix}

'''
Gets all custom user queries in the database.

Returns:
{
    'success': [
        {
            'name': string,
            'query': string,
            'postfix': string
        }
    ]
}
'''    
@application.route('/get_all_custom_queries')
def get_all_custom_queries():
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT * FROM Queries')
    except Exception as e:
        return {'error': str(e)}
    
    queries = [record for record in cursor]

    ret = list()
    for query in queries:
        temp = {
            'name': query[0],
            'query': query[1],
            'postfix': query[2]
        }
        ret.append(temp)

    cursor.close()
    connection.close()
    return {'success': ret}

'''
Executes all custom user queries in the database and returns the result.

Returns:
{
    'success': [
        {
            'query': {
                'name': string,
                'query': string,
                'postfix': string
            }
            'tickers': [
                string
            ]
        }
    ]
}
'''  
@application.route('/execute_all_custom_queries')
def execute_all_custom_queries():
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT * FROM Queries')
    except Exception as e:
        return {'error': str(e)}
    
    queries = [{'name': query[0], 'query': query[1], 'postfix': query[2]} for query in cursor]

    try:
        cursor.execute('SELECT * FROM Trackers')
    except Exception as e:
        return {'error': str(e)}
    
    tickers = [record[0] for record in cursor]

    ret = list()
    for query in queries:
        ret.append({'query': query, 'tickers': list()})
    
    for ticker in tickers:
        try:
            cursor.execute(
                '''
                SELECT *
                FROM Daily_Prices
                WHERE ticker = %s
                ORDER BY timestamp DESC
                '''
                ,
                [ticker]
            )
        except Exception as e:
            LOGGER.info(str({'query': query, 'ticker': ticker, 'error': e}))
            continue
        
        daily_prices = [record for record in cursor]

        try:
            cursor.execute(
                '''
                SELECT *
                FROM Minute_Prices
                WHERE ticker = %s
                ORDER BY timestamp DESC
                '''
                ,
                [ticker]
            )
        except Exception as e:
            LOGGER.info(str({'query': query, 'ticker': ticker, 'error': e}))
            continue
        
        minute_prices = [record for record in cursor]

        for i, query in enumerate(queries):
            result = util.evaluate_user_query(query['postfix'], daily_prices, minute_prices)

            if result == 1:
                ret[i]['tickers'].append(ticker)
            elif result == -1:
                LOGGER.info(str({'query': query, 'ticker': ticker, 'error': 'user query evaluation error'}))
    
    cursor.close()
    connection.close()
    return {'success': ret}

'''
Deletes a query.

Returns:
{
    'success': string - query deleted
}
'''  
@application.route('/delete_custom_query/<string:query>')
def delete_custom_query(query):
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute('DELETE FROM Queries WHERE query = %s', [query])
    except Exception as e:
        connection.rollback()
        return {'error': str(e)}
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': query}

# Cron job endpoint to call all user defined custom queries at the end of the trading day
@application.route('/email_all_custom_queries')
def email_all_custom_queries():
    print('Emailing custom queries')
    results = execute_all_custom_queries()
    if 'error' in results:
        LOGGER.error('Query execution went wrong...')
        return {'error': 'Error in query execution'}
    msg = ''
    for r in results['success']:
        msg += '\n'
        msg += 'query name: {}\nquery: {}\ntickers: {}\n'.format(r['query']['name'], r['query']['query'], r['tickers'])
    message = 'Subject: {}\n\n{}'.format('Custom Queries Notification', msg)
    util.send_volume_spike_notification(message)

    return {'success': 'sent emails for all custom queries', 'message': message}

# Cron job endpoint to update daily prices, news, and tweets
@application.route('/daily_tracker_updates')
def update_tracker_prices_and_tweets_and_news():
    LOGGER.info('WE IN THE SCHEDULER BOYS')

    if util.is_market_holiday(util.get_current_date(), session):
        return

    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ticker FROM Trackers")
    except Exception as e:
        return {'error': str(e)}
    tickers = [record[0] for record in cursor]
    cursor.close()
    connection.close()

    print('in scheduler got all tickers')
    for ticker in tickers:
        connection = util.connect_to_postgres()
        cursor = connection.cursor()
        try:
            cursor.execute("CALL remove_old_daily_price_data(%s);", (ticker,))
        except Exception as e:
            print({'error': e})
            connection.rollback()
        connection.commit()
        try:
            cursor.execute("CALL remove_old_minute_price_data(%s);", (ticker,))
        except Exception as e:
            print({'error': e})
            connection.rollback()
        connection.commit()
        cursor.close()
        connection.close()

        util.add_daily_closing_price(ticker, session)
        util.add_daily_minute_price(ticker, session)
        update_news(ticker)

    print('in scheduler successfully updated all data possible')
    return {'success': 'SUCESSFULLY UPDATED ALL PRICE AND TWEET DATA FOR ALL TRACKED TICKERS'}

# Cron job endpoint to update mongodb 
@application.route('/daily_mongo_updates')
def daily_mongo_updates():
    print('WE IN THE MONGO SCHEDULER')

    if util.is_market_holiday(util.get_current_date(), session):
        return
        
    connection = util.connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ticker FROM Trackers")
    except Exception as e:
        return {'error': str(e)}
    tickers = [record[0] for record in cursor]
    cursor.close()
    connection.close()

    col_ref = mongo_db['Live_Stock_Prices']

    # delete daily_prices older than a week and reset every minute_prices array and reset emas
    delete_before_timestamp = datetime.datetime.strptime(util.get_date_n_days_ago(7), '%Y-%m-%d')
    
    for tracker in col_ref.find():
        if 'usecase' not in tracker:
            col_ref.update_one(
            {
                'ticker': tracker['ticker']
            }, 
            {
                '$pull': { 'daily_prices': { 'timestamp': {'$lt': delete_before_timestamp } } },
                '$set': { 'minute_prices': [], 'minute_volume': [-1]*391, 'prev_ema': tracker['ema_volume'] }
            })
        else:
            col_ref.update_one({ 'usecase': 'af2' }, {'$set': { 'trackers_sent_today': [] } })

    print('in scheduler MONGO YEET')
    for ticker in tickers:
        url = '{}/v2/aggs/ticker/{}/prev?apiKey={}'.format(POLYGON_BASE_URL, ticker, POLYGON_API_KEY) 
        resp = util.polygon_get_request_multithreaded(url, session)
        if not resp or len(resp['results']) == 0:
            continue

        resp = resp['results'][0]
        timestamp = datetime.datetime.strptime(util.epoch_to_timestamp_format(resp['t']), '%Y-%m-%d %H:%M:%S')
        new_doc = {'volume': resp['v'], 'open': resp['o'], 'close': resp['c'], 'high': resp['h'], 'low': resp['l'], 'timestamp': timestamp}
        col_ref.update(
            { 'ticker': ticker },
            { '$push': { 'daily_prices': new_doc } }
        )

    print('UPDATED MONGO BOISSS')
    return {'success': 'SUCESSFULLY UPDATED ALL PRICE DATA FOR MONGO'}

'''
Note to self: Main method is not ran in Elastic Bean Stalk (by WSGI)
so don't add pertinent code inside of here. EB looks for a Flask object called
application inside of the WSGI path provided (defaulted to application.py) and runs
it on deployment by itself. We can keep this main method here for development purposes so
we don't have to run any flask commands locally.
'''
if __name__ == "__main__":
    application.run()