'''
# First grabs all fundamental info for SPY500 stocks as per the CSV and inserts into fundamentals table
@app.route('/get_all_fundamentals')
def grab_fundamentals():
    spy_500_tickers = util.read_spy_tickers()
    url1 = 'https://api.polygon.io/v1/meta/symbols/'
    url2 = '/company?apiKey=AKZYR3WO7U8B33F3O582'
    count = 0
    connection = connect_to_postgres()
    cursor = connection.cursor()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for ticker in spy_500_tickers:
            futures.append(executor.submit(util.polygon_get_request_multithreaded, url1+ticker+url2, session))
        with open ('fundamental_data.csv', 'w+', newline='') as csv_file:
            write = csv.writer(csv_file, delimiter=',')
            for future in concurrent.futures.as_completed(futures):
                resp = future.result()
                if not resp:
                    continue
                # must hardcode 0 marketcap when NULL is returned from API for that field
                if not resp['marketcap']:
                    resp['marketcap'] = 0
                fundamentals = [resp['symbol'], resp['name'], resp['industry'], resp['sector'], resp['marketcap'], resp['description']]
                write.writerow(fundamentals)
                count += 1
                print(count)
        csv_file = open('fundamental_data.csv', 'r')
        cursor.copy_expert("copy Fundamentals from stdin (format csv)", csv_file)
        csv_file.close()
    os.remove('fundamental_data.csv')
    connection.commit()
    cursor.close()
    connection.close()
    return 'SUCCESSFULLY ADDED ALL FUNDAMENTALS FOR SPY 500 STOCKS!'
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

'''
# function that inserts new closing price data for each stock in Prices table and also removes any entries outside of 50 days
@app.route('/update_daily_prices')
def update_daily_prices():
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
            futures.append(executor.submit(polygon_get_request_multithreaded, url1+ticker+url2))
        with open ('price_data.csv', 'w+', newline='') as csv_file:
            write = csv.writer(csv_file)
            for future in concurrent.futures.as_completed(futures):
                return 'asd'
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
    return 'SUCCESSFULLY UPDATED PRICES UP TO' + ' ' + util.get_current_date()
'''