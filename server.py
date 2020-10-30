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

# helper function for get request multithreading
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