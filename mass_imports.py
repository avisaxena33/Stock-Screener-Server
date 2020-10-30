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