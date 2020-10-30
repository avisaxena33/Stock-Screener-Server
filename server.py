import sys
import boto3
import psycopg2
from flask import Flask
import util
import requests 
import concurrent.futures

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

# Tracks a new ticker if not already tracked and adds price data
@app.route('/add_tracker/<string:ticker>')
def add_tracker(ticker):
    ticker = ticker.upper()
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute("CALL add_tracker(%s);", (ticker,))
    except Exception as e:
        return str(e)
    if not util.add_daily_price_data(ticker, session, connection, cursor) or not util.add_minute_price_data(ticker, session, connection, cursor):
        cursor.close()
        connection.close()
        return 'COULD NOT ADD PRICE DATA FOR' + ' ' + ticker
    connection.commit()
    cursor.close()
    connection.close()
    return 'Successfully added the selected ticker!'

# Removes a ticker that is being tracked alongisde all the price data for that ticker
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

# NEED TO CHANGE THIS TO RETURN THE CORRECT PRICE DATA (HASN'T BEEN DECIDED YET?)
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

