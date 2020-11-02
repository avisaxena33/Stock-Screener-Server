import sys
import boto3
import psycopg2
from flask import Flask
import util
import requests 
import concurrent.futures

from config import *

# Flask class reference
app = Flask(__name__)
session = requests.Session()

# Attempts to connect to database and returns connection object if successsful
def connect_to_postgres(): 
    try:
        return psycopg2.connect(host=DB_ENDPOINT, port=PORT, dbname=DB_NAME, user=MASTER_USERNAME, password=MASTER_PASSWORD)
    except Exception as e:
        print("Database connection failed due to {}".format(e))   

# testing flask rest calls
@app.route("/")
def hello():
    return 'hello'

# Tracks a new ticker if not already tracked and adds price data
@app.route('/add_tracker/<string:ticker>')
def add_tracker(ticker):
    ticker = ticker.upper()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL add_tracker(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    if not util.add_daily_price_data(ticker, session, connection, cursor) or not util.add_minute_price_data(ticker, session, connection, cursor):
        cursor.close()
        connection.close()
        return {'error': 'COULD NOT ADD PRICE DATA FOR' + ' ' + ticker}
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': 'Successfully added the selected ticker!'}

# Removes a ticker that is being tracked alongisde all the price data for that ticker
@app.route('/remove_tracker/<string:ticker>')
def remove_tracker(ticker):
    ticker = ticker.upper()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_tracker(%s);", (ticker,))
    except Exception as e:
        return {'error': str(e)}
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': 'Successfully removed the selected ticker!'}

# Returns a list of all available tickers to track
@app.route('/get_all_tickers')
def get_all_tickers():
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ticker FROM Fundamentals")
    except Exception as e:
        return {'error': str(e)}
    tickers = [record[0] for record in cursor]
    connection.commit()
    cursor.close()
    connection.close()
    return {'success': tickers}

# NEED TO CHANGE THIS TO RETURN THE CORRECT PRICE DATA (HASN'T BEEN DECIDED YET?)
# Grabs all currently tracked stocks most recently updated price data
@app.route('/get_trackers')
def get_trackers():
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM Trackers T1 NATURAL JOIN Minute_Prices P1 NATURAL JOIN Fundamentals F1 WHERE P1.timestamp = (SELECT MAX(P2.timestamp) FROM Minute_Prices P2 WHERE P2.ticker = P1.ticker)")
    except Exception as e:
        return str(e)
    tracked_raw_data = [record for record in cursor]
    if not tracked_raw_data or len(tracked_raw_data) == 0:
        return 'No stocks are currently being tracked'
    tracked_stocks = []
    for stock in tracked_raw_data:
        curr_stock_map = {'ticker': stock[0], 'timestamp': stock[1], 'open': stock[2], 'close': stock[3], 'high': stock[4], 'low': stock[5], 'volume': stock[6],
        'company_name': stock[7], 'industry': stock[8], 'sector': stock[9], 'market_cap': stock[10], 'description': stock[11]}
        tracked_stocks.append(curr_stock_map)
    cursor.close()
    connection.close()
    return {'tracked': tracked_stocks}

# gets 3 news articles for a ticker (can modify to return 50)



# gets {fundamentals, prices(1d,...,1y), news} for one ticker
@app.route('/get/<string:ticker>')
def get_ticker_data(ticker):
    connection = connect_to_postgres()
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
            ORDER BY date DESC
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
            'volume': fundamentals[0],
            'company_name': fundamentals[1], 
            'industry': fundamentals[2], 
            'sector': fundamentals[3], 
            'market_cap': fundamentals[4], 
            'description': fundamentals[5]
        },
        'news': [
            {
                'title':'need implement'
            },
        ]
    }

    curday = util.get_current_date_datetime()
    datetime5d = util.get_date_n_days_ago_datetime(7)
    datetime1m = util.get_date_n_days_ago_datetime(31)
    datetime3m = util.get_date_n_days_ago_datetime(62)
    datetime6m = util.get_date_n_days_ago_datetime(183)

    for day in daily_prices:
        temp_datetime = util.d2dt(day[1])
        temp = {
            'timestamp': temp_datetime,
            'open': day[2],
            'close': day[3],
            'high': day[4],
            'low': day[5]
        }
        if temp_datetime > datetime5d:
            ticker_data['prices']['5d'].append(temp)
        if temp_datetime > datetime1m:
            ticker_data['prices']['1m'].append(temp)
        if temp_datetime > datetime3m:
            ticker_data['prices']['3m'].append(temp)
        if temp_datetime > datetime6m:
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
    
    cursor.close()
    connection.close()
    return ticker_data
