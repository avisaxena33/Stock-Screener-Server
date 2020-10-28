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
    ticker = ticker.lower()
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
    ticker = ticker.lower()
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

# Grabs all currently tracked stocks and their fundamentals
@app.route('/get_trackers')
def get_trackers():
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM Trackers")
    except Exception as e:
        return str(e)
    tracked_stocks = [record for record in cursor]
    cursor.close()
    connection.close()
    return {'tracked': tracked_stocks}

'''
# First grabs all Stocks in US with tickers that are active (35,171) then grabs all the ones that have fundamental info matching the same ticker symbol
# (8486) and inserts into fundamentals table
@app.route('/get_fundamentals')
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

def get_price_tmp(url):
    resp = session.get(url)
    return json.loads(resp.text)

@app.route('/get_prices')
def get_prices():
    tickers = set()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    cursor.execute("SELECT ticker FROM Fundamentals")
    tickers = {record[0] for record in cursor}
    url1 = 'https://api.polygon.io/v2/aggs/ticker/'
    url2 = '/range/1/day/2020-09-03/2020-10-23?sort=asc&apiKey=AKZYR3WO7U8B33F3O582'
    count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for ticker in tickers:
            futures.append(executor.submit(get_price_tmp, url1+ticker+url2))
        with open ('price_data.csv', 'w+', newline='') as csv_file:
            write = csv.writer(csv_file)
            for future in concurrent.futures.as_completed(futures):
                resp = future.result()
                curr_ticker = resp['ticker']
                resp = resp['results']
                if not resp or len(resp) == 0:
                    continue
                for day in resp:
                    db_timestamp_format = datetime.datetime.utcfromtimestamp(int(day['t'])/1000).strftime('%Y-%m-%d %H:%M:%S')
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