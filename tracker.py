import sys
import boto3
import psycopg2
from flask import Flask, Blueprint
from polygon import RESTClient
import requests 
import json
import datetime
import concurrent.futures
import csv
import os

tracker = Blueprint('tracker', __name__,
                        template_folder='templates')

# Tracks a new ticker if not already tracked
@app.route('/add/<string:ticker>')
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
@tracker.route('/remove/<string:ticker>')
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
@app.route('/get_all')
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

@app.route('/get/<string:ticker>')
def get_ticker_data(ticker):
    connection = connect_to_postgres()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f'''
            SELECT *
            FROM Trackers T NATURAL JOIN Daily D NATURAL JOIN Fundamentals F
            WHERE ticker = {ticker}
            '''
        )
    except Exception as e:
        return str(e)

    fundamentals = cursor[0] if cursor else None

    try:
        cursor.execute(
            f'''
            SELECT *
            FROM Trackers T NATURAL JOIN Daily D
            WHERE ticker = {ticker}
            ORDER BY timestamp
            '''
        )
    except Exception as e:
        return str(e)

    daily_prices = [record for record in cursor]

    try:
        cursor.execute(
            f'''
            SELECT *
            FROM Trackers T NATURAL JOIN Minute M
            WHERE ticker = {ticker}
            ORDER BY timestamp
            '''
        )
    except Exception as e:
        return str(e)

    minute_prices = [record for record in cursor]

    if not fundamentals:
        return {'error': 'No fundamental data found'}
    if not daily_prices:
        return {'error': 'No daily_prices data found'}
    if not minute_prices:
        return {'error': 'No minute_prices data found'}
    
    ticker_data = {
        'prices': {
            '1d': list()
            '5d': list()
            '1m': list()
            '3m': list()
            '6m': list()
            '1y': list()
        },
        'fundamentals': {
            'volume': stock[6],
            'company_name': stock[7], 
            'industry': stock[8], 
            'sector': stock[9], 
            'market_cap': stock[10], 
            'description': stock[11]
        }
    }

    
    for stock in tracked_raw_data:
        temp = {'timestamp': stock[1].strftime('%Y-%m-%d'), 'open': stock[2], 'close': stock[3], 'high': stock[4], 'low': stock[5], }
        ticker_data.append(temp)
    cursor.close()
    connection.close()
    return {'tracked': tracked_stocks}
