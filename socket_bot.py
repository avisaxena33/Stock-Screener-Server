import websocket, requests, json
import pytz
import time
import util
import pymongo
import datetime

from config import *
import logging.handlers

# socket
DATA_SOCKET = 'wss://socket.polygon.io/stocks'

def on_open(ws):
    LOGGER.info('opening connection')
    auth_data = {
        'action': 'auth',
        'params': POLYGON_API_KEY
    }
    ws.send(json.dumps(auth_data))

def on_message(ws, message):
    message = json.loads(message)[0]
    print(message)
    if message['ev'] == 'AM':
        process_price_data(message)
        pass
    elif message['ev'] == 'status':
        if message['status'] != 'auth_success':
            return
        # LOGGER.info('status message: ' + message['message'])
        connection = util.connect_to_postgres()
        cursor = connection.cursor()
        try:
            cursor.execute('SELECT ticker FROM Trackers')
        except Exception as e:
            LOGGER.error('error :' + str(e))
        all_tickers = ['AM.'+record[0] for record in cursor]

        listen_message = {
            'action': 'subscribe',
            'params': ','.join(all_tickers)
        }
        ws.send(json.dumps(listen_message))
    else:
        LOGGER.info('unexpected message: ' + message)

def on_close(ws):
    LOGGER.info('connection closed, restarting connection')
    run_bot()

def on_error(ws, error):
    LOGGER.error('received error: ' + str(error))

def process_price_data(prices):
    col_ref = mongo_db['Live_Stock_Prices']
    print(util.get_ema_idx(prices['s']))
    if prices and util.within_trading_hours(prices['s']):
        timestamp = datetime.datetime.strptime(util.epoch_to_timestamp_format(prices['s']), '%Y-%m-%d %H:%M:%S')
        new_price = {'volume': prices['v'], 'open': prices['o'], 'close': prices['c'], 'high': prices['h'], 'low': prices['l'], 'timestamp': timestamp}

        col_ref.update(
            { 'ticker': prices['sym'] },
            { '$push': { 'minute_prices': new_price } }
        )

        on_minute(prices)
        is_vol_spike = volume_spike_detection(prices['sym'], prices)
        af2_doc = col_ref.find_one({'usecase': 'af2'})
        trackers_sent_today = af2_doc['trackers_sent_today']
        if is_vol_spike and prices['sym'] not in trackers_sent_today:
            trackers_sent_today.append(prices['sym'])
            col_ref.update_one( { 'usecase': 'af2' }, {'$set': {'trackers_sent_today': trackers_sent_today } } )
            msg = 'There is a EMA volume spike on ' + prices['sym'] + ' at ' + util.get_current_date()
            message = 'Subject: {}\n\n{}'.format('EMA Volume Spike Notification', msg)
            util.send_volume_spike_notification(message)

def run_bot():
    LOGGER.info('WE IN THE BOT FIRST LINE')
    #websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        DATA_SOCKET,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    LOGGER.info('WE IN THE RUN_BOT ...')
    ws.run_forever()

# updates aggregate volume data for a tracked stock every time new minute data is received
def on_minute(new_minute_data):
    LOGGER.info('IN ON_MINUTE BOIS')
    curr_ticker = new_minute_data['sym']
    curr_vol = new_minute_data['av']

    col_ref = mongo_db['Live_Stock_Prices']
    doc_data = col_ref.find_one({'ticker': curr_ticker})
    prev_ema = doc_data['prev_ema']
    ema_volume = doc_data['ema_volume']
    minute_volume = doc_data['minute_volume']

    LOGGER.info('WE LOGGING MINUTE_VOL BOISSS')

    idx = util.get_ema_idx(new_minute_data['s'])
    if idx < 0 or idx >= 391:
        return
    
    minute_volume[idx] = curr_vol
    if ema_volume[idx] < 0:
        ema_volume[idx] = curr_vol
    else:
        ema_volume[idx] = (ALPHA*ema_volume[idx]) + ((1-ALPHA)*minute_volume[idx])
    # if prev_ema[idx] < 0:
    #     prev_ema[idx] = ema_volume[idx]

    LOGGER.info('WE UPDATING MONGODB VOLUME BOIIISSSS')
    col_ref.update_one({'ticker': curr_ticker}, {'$set': {'ema_volume': ema_volume, 'minute_volume': minute_volume, 'prev_ema': prev_ema } } )

# checks ema volume spike after every new aggregate minute data for a stock is received
def volume_spike_detection(ticker, new_minute_data):
    col_ref = mongo_db['Live_Stock_Prices']
    doc_data = col_ref.find_one({'ticker': ticker})
    prev_ema = doc_data['prev_ema']
    ema_volume = doc_data['ema_volume']

    idx = util.get_ema_idx(new_minute_data['s'])
    if idx < 0 or idx >= 391:
        return

    if prev_ema[idx] < 0:
        return False
    else:
        threshold = prev_ema[idx]*MULTIPLIER
        condition = ema_volume[idx] > threshold
    return condition