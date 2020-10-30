import sys
import boto3
import psycopg2
from flask import Flask
from polygon import RESTClient
import requests 
import json
import datetime
import concurrent.futures
import csv
import os

# Flask class reference
app = Flask(__name__)
session = requests.Session()

# Environment variables
ENDPOINT="stock-screener-2.c1h93r1ybkd8.us-west-2.rds.amazonaws.com"
PORT="5432"
USR="Administrator"
REGION="us-west-2"
DBNAME="postgres"

# This looks bad I know C:
MASTER_USERNAME = 'buffoon_squad'
MASTER_PASSWORD = 'Sharingan_Amaterasu33'

# Polygon API Key
key = "hTrh4n_vtmgDjJjdf1rwWtjkw7PJIa1b"
albert_key = 'AKZYR3WO7U8B33F3O582'

# Attempts to connect to database and returns connection object if successsful
def connect_to_postgres(): 
    try:
        return psycopg2.connect(host=ENDPOINT, port=PORT, dbname=DBNAME, user=MASTER_USERNAME, password=MASTER_PASSWORD)
    except Exception as e:
        print("Database connection failed due to {}".format(e))   

# testing flask rest calls
@app.route("/")
def hello():
    return 'hello'

# Tracks a new ticker if not already tracked
@app.route('/add_tracker/<string:ticker>')
def add_tracker(ticker):
    ticker = ticker.upper()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL add_tracker(%s);", (ticker,))
    except Exception as e:
        return str(e)
    connection.commit()
    cursor.close()
    connection.close()
    return 'Successfully added the selected ticker!'

# Removes a ticker that is being tracked
@app.route('/remove_tracker/<string:ticker>')
def remove_tracker(ticker):
    ticker = ticker.upper()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_tracker(%s);", (ticker,))
    except Exception as e:
        return str(e)
    connection.commit()
    cursor.close()
    connection.close()
    return 'Successfully removed the selected ticker!'

# Grabs all currently tracked stocks most recently updated price data
@app.route('/get_trackers')
def get_trackers():
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM Trackers T1 NATURAL JOIN Prices P1 NATURAL JOIN Fundamentals F1 WHERE P1.timestamp = (SELECT MAX(P2.timestamp) FROM Prices P2 WHERE P2.ticker = P1.ticker)")
    except Exception as e:
        return str(e)
    tracked_raw_data = [record for record in cursor]
    if not tracked_raw_data or len(tracked_raw_data) == 0:
        return 'No stocks are currently being tracked'
    tracked_stocks = []
    for stock in tracked_raw_data:
        curr_stock_map = {'ticker': stock[0], 'timestamp': stock[1].strftime('%Y-%m-%d'), 'open': stock[2], 'close': stock[3], 'high': stock[4], 'low': stock[5], 'volume': stock[6],
        'company_name': stock[7], 'industry': stock[8], 'sector': stock[9], 'market_cap': stock[10], 'description': stock[11]}
        tracked_stocks.append(curr_stock_map)
    cursor.close()
    connection.close()
    return {'tracked': tracked_stocks}

# returns current date string in YYYY-MM-DD format
def get_current_date():
    return datetime.datetime.today().strftime('%Y-%m-%d')

# returns date fifty days ago from today in YYYY-MM-DD format
def get_date_fifty_days_ago():
    current_date = datetime.datetime.now()
    delta = datetime.timedelta(days = 50)
    fifty_days_ago = current_date - delta
    return fifty_days_ago.strftime('%Y-%m-%d')

# helper function for multithreading that grabs aggregate price data for given stock and 50 day range
def get_price_tmp(url):
    resp = session.get(url)
    return json.loads(resp.text)

# function that inserts new closing price data for each stock in Prices table and also removes any entries outside of 50 days
@app.route('/daily_update_prices')
def daily_update_prices():
    tickers = set()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL remove_old_price_data();", ())
    except Exception as e:
        return str(e)
    cursor.execute("SELECT DISTINCT ticker FROM Prices")
    tickers = {record[0] for record in cursor}
    url1 = 'https://api.polygon.io/v2/aggs/ticker/'
    url2 = '/prev?apiKey=AKZYR3WO7U8B33F3O582'
    count = 0
    csv_unique_name = get_current_date() + '_price_data.csv'
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for ticker in tickers:
            futures.append(executor.submit(get_price_tmp, url1+ticker+url2))
        with open ('price_data.csv', 'w+', newline='') as csv_file:
            write = csv.writer(csv_file)
            for future in concurrent.futures.as_completed(futures):
                resp = future.result()
                if not resp or resp['status'] != 'OK' or len(resp['results']) == 0:
                    continue
                resp = resp['results'][0]
                db_timestamp_format = datetime.datetime.utcfromtimestamp(int(resp['t'])/1000).strftime('%Y-%m-%d')
                # handles case where current day's closed is not returned from api for whatever reason
                if db_timestamp_format != get_current_date():
                    continue
                prices = [resp['T'], db_timestamp_format, resp['o'], resp['c'], resp['h'], resp['l'], resp['v']]
                write.writerow(prices)
                print(count)
                count += 1
        csv_file = open('price_data.csv', 'r')
        cursor.copy_from(csv_file, 'Prices', sep=',', columns=('ticker', 'timestamp', 'open', 'close', 'high', 'low', 'volume'))
        csv_file.close()
    os.remove('price_data.csv')
    connection.commit()
    cursor.close()
    connection.close()
    return 'SUCCESSFULLY UPDATED PRICES UP TO' + ' ' + get_current_date()

'''
# First grabs all Stocks in US with tickers that are active (35,171) then grabs all the ones that have fundamental info matching the same ticker symbol
# (8486) and inserts into fundamentals table
@app.route('/get_all_fundamentals')
def grab_fundamentals():
    url1 = 'https://api.polygon.io/v2/reference/tickers?sort=ticker&market=STOCKS&locale=us&perpage=50&page='
    url2 = '&active=true&apiKey=AKZYR3WO7U8B33F3O582'
    tickers = set()
    for i in range(1, 705):
        curr_url = url1 + str(i) + url2 
        r = requests.get(curr_url)
        resp = json.loads(r.text)['tickers']
        for ticker_data in resp:
            tickers.add(ticker_data['ticker'])
    if len(tickers) > 35171:
        return 'Missing some stocks'

    det_url1 = 'https://api.polygon.io/v1/meta/symbols/'
    det_url2 = '/company?apiKey=AKZYR3WO7U8B33F3O582'
    connection = connect_to_postgres()
    cursor = connection.cursor()
    for ticker in tickers:
        det_url = det_url1 + ticker + det_url2
        r = requests.get(det_url)
        if r.status_code != 200:
            continue
        resp = json.loads(r.text)
        fundamentals = (resp['symbol'], resp['name'], resp['industry'], resp['sector'], resp['marketcap'], resp['description'])
        try:
            cursor.execute('INSERT INTO Fundamentals (ticker, name, industry, sector, market_cap, description) VALUES (%s, %s, %s, %s, %s, %s)', fundamentals)
        except Exception as e:
            return str(e)
    connection.commit()
    cursor.close()
    connection.close()
    return 'SUCCESSFULLY ADDED ALL FUNDAMENTALS'
'''

'''
# Function that grabs all possible price day (50 day range hardcoded to specific dates) and writes it to CSV and ports it to PostgreSQL (one time thing)
# Please dont spam run this -- it pulls and writes ~200k+ records and it's expensive!!!
@app.route('/get_prices')
def get_prices():
    tickers = set()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    cursor.execute("SELECT ticker FROM Fundamentals")
    tickers = {record[0] for record in cursor}
    url1 = 'https://api.polygon.io/v2/aggs/ticker/'
    url2 = '/range/1/day/'
    url3 = '?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    date_high = get_current_date()
    date_low = get_date_fifty_days_ago()
    sub_url = url2 + date_low + '/' + date_high + url3
    # order is: url1 + ticker + sub_url
    count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for ticker in tickers:
            futures.append(executor.submit(get_price_tmp, url1+ticker+sub_url))
        with open ('price_data.csv', 'w+', newline='') as csv_file:
            write = csv.writer(csv_file)
            for future in concurrent.futures.as_completed(futures):
                resp = future.result()
                curr_ticker = resp['ticker']
                resp = resp['results']
                if not resp or len(resp) == 0:
                    continue
                for day in resp:
                    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(day['t'])/1000).strftime('%Y-%m-%d')
                    prices = [curr_ticker, db_timestamp_format, day['o'], day['c'], day['h'], day['l'], day['v']]
                    write.writerow(prices)
                print(count)
                count += 1
        csv_file = open('price_data.csv', 'r')
        cursor.copy_from(csv_file, 'Prices', sep=',', columns=('ticker', 'timestamp', 'open', 'close', 'high', 'low', 'volume'))
    connection.commit()
    cursor.close()
    connection.close()
    return 'SUCCESSFULLY ADDED ALL PRICES'
'''