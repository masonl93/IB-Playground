import argparse
import datetime
import pathlib
import queue
import sys
import time
import xml.etree.ElementTree as ET

import pandas

import InteractiveBrokers as ib
import Algorithms as algo
import Ratios
from ContractSamples import ContractSamples
from Black_Scholes import BlackScholes


# Constants
SAVE_FILE = 'save_from_sell.txt'



"""
Alpha within Factors
"""
def alphaInFactors(app, tickers, input_f):

    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    # Remove me later!
    # tickers = tickers[:80]

    ticker_data = {}
    issue_tickers = {}
    prices = []

    ticker_data, issue_tickers = getPriceData(app, tickers)
    fund_ticker_data, data_issue_tickers = getFundamentalData(app, tickers)

    # Create our dataframe with price and fundamental data
    symbols = []
    prices = []
    datas = []
    for key, val in ticker_data.items():
        symbols.append(key)
        prices.append(val)
        if key in fund_ticker_data:
            datas.append(fund_ticker_data[key])
        else:
            datas.append(None)
    data = {'Symbol': symbols, 'Price': prices, 'Data': datas, 'Market Cap': None, 'Enterprise Value': None,
            'Dividend': None, 'Momentum': None, 'Change in NOA': None, 'EPS Growth': None,'P/E': None, 'EV/EBITDA': None,
            'EV/S': None, 'EV/FCF': None, 'Debt to Equity': None}
    df = pandas.DataFrame(data=data).dropna(subset=['Price', 'Data'])
    print("Price Data:")
    print(df)

    # Loop through dataframe and update specific values
    for i, row in df.iterrows():
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(row['Data'], quarterly=True)
        # Getting annual reports also
        current_annual, prev_annual = app.parseFinancials(row['Data'])

        df.at[i, 'Dividend'] = Ratios.getDivPayout(qtr1, qtr2)

        # Numerators
        df.at[i, 'Market Cap'], ev = Ratios.getCompanyValues(row['Price'], qtr1)[::2]
        df.at[i, 'Enterprise Value'] = ev

        df.at[i, 'P/E'] = Ratios.getP_E(row['Price'], qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/EBITDA'] = Ratios.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/S']  = Ratios.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/FCF']  = Ratios.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)

        df.at[i, 'Change in NOA'] = Ratios.calcChangeInNOA(current_annual, prev_annual)
        df.at[i, 'EPS Growth'] = Ratios.calcOneYearGrowth(current_annual, prev_annual)
        df.at[i, 'Debt to Equity'] = Ratios.calcDebtToEquity(qtr1)

    # Drop rows where we don't have market cap or EV
    df = df.dropna(subset=['Market Cap', 'Enterprise Value'])
    print(df)

    df = algo.compositeValueRank(df)
    print('All stocks ranked by value score:')
    print(df)
    cutoff = int(df.shape[0]*4/5)
    df = df[:-cutoff]
    df = df.reset_index(drop=True,)
    print('Top quintile of value score:')
    print(df)

    # Value Traps
    # Growth (eps change), Earnings quality (change in NOA), and Leverage (debt to equity) calculated above
    # Getting historical data for calculating Momentum: trailing 6 months return
    hist_data, hist_issue_tickers = getHistData(app, list(df['Symbol'].values), "6 M")

    # Update df with momentum values
    for i, row in df.iterrows():
        if row['Symbol'] in hist_data:
            df.at[i, 'Momentum'] = algo.calcTotalReturn(hist_data[row['Symbol']].iloc[0]['price'], row['Price'], row['Dividend'])
        else:
            df.at[i, 'Momentum'] = None

    # Sort and Remove Bottom Deciles
    columns = ['Momentum', 'Debt to Equity', 'EPS Growth', 'Change in NOA']
    for column in columns:
        if df[column].dtype == 'object':
            df = df[df[column] != None]
        if column == 'Momentum' or column == 'EPS Growth':
            df = df.sort_values(column, ascending=False)
        else:
            df = df.sort_values(column)
        cutoff = int(df.shape[0]/10)
        if cutoff == 0:
            cutoff = 1
        df = df[:-cutoff]

    df = df.sort_values('Value Score', ascending=False)
    df = df.drop(columns=['Data'])
    df = df.reset_index(drop=True,)
    print('Final Results:')
    with pandas.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
    print(df)

    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)
    print('Tickers missing historical data: (%s)' % len(hist_issue_tickers))
    print(hist_issue_tickers)
    return


"""
Ratio Calculator
    - README usage and algo sections, etc
    - Sketchy Accounting detection: Use Beneish's M-Score or Montier's C-Score (see gmtresearch.com)
    - Bankruptcy Risk: Altman Z-Score
    - Tobins Q, other scores that GW investors use
    - Create a final row in dataframe for averages
"""
def ratios(app, tickers):

    ticker_data, issue_tickers = getPriceData(app, tickers)
    fund_ticker_data, data_issue_tickers = getFundamentalData(app, tickers)

    # Create our dataframe with price and fundamental data
    symbols = []
    prices = []
    datas = []
    for key, val in ticker_data.items():
        symbols.append(key)
        prices.append(val)
        if key in fund_ticker_data:
            datas.append(fund_ticker_data[key])
        else:
            datas.append(None)
    data = {'Symbol': symbols, 'Price': prices, 'Data': datas, 'Market Cap': None, 'Firm Value': None,
            'Enterprise Value': None, 'P/E': None, 'EV/EBITDA': None,
            'P/B': None, 'EV/S': None, 'EV/FCF': None}
    df = pandas.DataFrame(data=data).dropna(subset=['Price', 'Data'])

    # Loop through dataframe and update specific values
    for i, row in df.iterrows():
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(row['Data'], quarterly=True)

        # Numerators
        df.at[i, 'Market Cap'], df.at[i, 'Firm Value'], ev = Ratios.getCompanyValues(row['Price'], qtr1)
        df.at[i, 'Enterprise Value'] = ev

        df.at[i, 'P/E'] = Ratios.getP_E(row['Price'], qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/EBITDA'] = Ratios.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/S']  = Ratios.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/FCF']  = Ratios.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'P/B'] = Ratios.getP_B(row['Price'], qtr1)

    df = df.drop(columns=['Data'])
    print('Results:')
    with pandas.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
    print(df)

    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)
    return


"""
BS warrants
    - any todos from old repo?
    - add readme to this repo readme
    - proper tests
    - Use yield of T-bill closest to expiry date as risk value
    - add support for list/input file of tickers
"""
def warrants(app, tickers, warrants_out):
    if tickers is None:
        print('Error: Must provide ticker for warrant valuation')
        return

    if warrants_out is None:
        print('Number of warrants outstanding was not provided. Will not calculate with share dilution.')

    # Take user input for vol?
    vols = [.2, .3, .35, .4, .5, .6]
    data = {'Volatility': vols}

    ticker_data, issue_tickers = getPriceData(app, tickers)
    fund_ticker_data, data_issue_tickers = getFundamentalData(app, tickers)

    for key, val in ticker_data.items():
        # find the warrant
        app.getContractDetails(key, "WAR", exchange='SMART', currency='USD')
        underlying_price = float(val)
        # TODO: contract yield never will be updated, need to actually get this figure
        div = app.contract_yield
        qtr1 = app.parseFinancials(fund_ticker_data[key], quarterly=True)[0]
        shares_out = qtr1['total_common_shares_outstanding']

        # Wait on contract details
        while not app.contract_details_flag:
            pass
        for c in app.contract_details:
            contract = c.contract
            strike = contract.strike
            # right = contract.right
            warrants_per_share = (1/float(contract.multiplier))
            expiry = datetime.datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d').strftime('%m-%d-%Y')

            # TODO: Get this from t-bill near expiry date?
            risk = .03

            prices = []
            for vol in vols:
                # TODO: remove the repetitive prints here
                print(strike, underlying_price, risk, vol,
                                expiry, div, shares_out, warrants_out,
                                warrants_per_share)
                bs = BlackScholes(strike, underlying_price, risk, vol,
                                expiry, div, shares_out, warrants_out,
                                warrants_per_share)
                prices.append('$' + str(round(bs.price_euro_call(), 5)))
            header = ('%s %s' % (str(strike), expiry))
            data[header] = prices
        df = pandas.DataFrame(data=data)
        print(df)

    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)


"""
Factors
"""
def factorSort(app, tickers, rank, input_f):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    fund_ticker_data, data_issue_tickers = getFundamentalData(app, tickers)
    datas = []
    for ticker in tickers:
        if type(ticker) is list and ticker[0] in fund_ticker_data:
            # Foreign stock
            datas.append(fund_ticker_data[ticker[0]])
        elif ticker in fund_ticker_data:
            datas.append(fund_ticker_data[ticker])
        else:
            datas.append(None)

    data = {'Symbol': tickers, 'Data': datas, 'Change in NOA': None, '1yr Debt Change': None,
            'Debt to Equity': None, 'ROIC': None}
    df = pandas.DataFrame(data=data).dropna(subset=['Data'])

    for i, row in df.iterrows():
        print(row['Symbol'])
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(row['Data'], quarterly=True)
        current_annual, prev_annual = app.parseFinancials(row['Data'])
        df.at[i, 'Change in NOA'] = Ratios.calcChangeInNOA(current_annual, prev_annual)
        df.at[i, 'Debt to Equity'] = Ratios.calcDebtToEquity(qtr1)
        df.at[i, 'ROIC'] = Ratios.calcROIC(qtr1, qtr2, qtr3, qtr4)
        df.at[i, '1yr Debt Change'] = Ratios.calcDebtChange(current_annual, prev_annual)

    df = df.drop(columns=['Data'])
    print(df)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)

    if rank:
        print('Ranked Results - Remove Lowest Decile for each Factor:')
        columns = ['Change in NOA', 'Debt to Equity', 'ROIC', '1yr Debt Change']
        for column in columns:
            if df[column].dtype == 'object':
                df = df[df[column] != None]
            if column == 'ROIC':
                df = df.sort_values(column, ascending=False)
            else:
                df = df.sort_values(column)
            cutoff = int(df.shape[0]/10)
            if cutoff == 0:
                cutoff = 1
            df = df[:-cutoff]

        # Getting AVG
        df.loc[-1] = ['Averages', df['Change in NOA'].mean(), df['1yr Debt Change'].mean(), df['Debt to Equity'].mean(), df['ROIC'].mean()]
        print(df.reset_index(drop=True,))


"""
MA Cross
    - histData limits: 60 req/10min?
"""
def movingAvgCross(app, tickers, start, buy):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    if start is not None:
        start_index = tickers.index(start) + 1
        tickers = tickers[start_index:]

    contract = app.createContract(None, "STK", "USD", "SMART", "ISLAND")

    for ticker in tickers:
        contract.symbol = ticker

        # Only process if no open orders with this ticker
        if app.orders_df.empty or not app.orders_df['symbol'].str.contains(ticker).any():
            app.getHistoricalData(contract, "1 Y")

            print("Symbol: " + ticker)
            waitForData(app, 'hist')
            # Golden Cross and not in portfolio -> buy
            if algo.movingAvgCross(app.hist_data_df) and not app.portfolioCheck(ticker):
                print('Placing Buy Order for: ' + ticker)
                if buy:
                    amt = app.calcOrderSize(float(app.hist_data_df.tail(1)['price']), 1000)
                    order = ib.Order()
                    order.action = "BUY"
                    order.orderType = "MKT"
                    order.totalQuantity = amt
                    app.place_order(contract, order)
            # Death cross and in portfolio -> sell
            elif (app.portfolioCheck(ticker) and not algo.movingAvgCross(app.hist_data_df)):
                print('Placing Sell Order for: ' + ticker)
                if buy:
                    app.sellPosition(ticker, 'STK')
            app.resetData()


"""
Cache Data

    Saves a dataframe to file in pickle format for use on a later run.
"""
def cacheData(df, input_f, algo):
    results_file = input_f + '.pickle.' + algo
    df.to_pickle(results_file)


"""
TODO: update with comments
"""
def processQueue(q, tickers, app, q2=None):
    data_map = {}
    issues = {}

    while True:
        if q.empty():
            # Once our queue is empty and we have processed all tickers
            # we can break out of this loop
            if (len(data_map) + len(issues) >= len(tickers)):
                break
            elif q2 is not None:
                # Live price data queue is empty but haven't processed all tickers
                # Lets use last close price as maybe no shares have traded today
                while True:
                    try:
                        data, reqId = q2.get(block=False)
                        symbol = app.reqId_map[reqId]
                        if symbol not in data_map and symbol not in issues:
                            print("Using Backup Queue for: " + symbol)
                            data_map[symbol] = data
                    except queue.Empty:
                        break
        try:
            # Symbol caused an error i.e. No security definition for the symbol
            error, reqId = app.data_errors_q.get(block=False)
            symbol = app.reqId_map[reqId]
            print('Bad Symbol: ' + symbol)
            print("Error: " + error)
            issues[symbol] = error

        except queue.Empty:
            pass

        try:
            # Get data from queue
            data, reqId = q.get(block=False)
            symbol = app.reqId_map[reqId]
            data_map[symbol] = data
        except queue.Empty:
            continue

    return data_map, issues


'''
TODO: update with comments
'''
def getPriceData(app, tickers):
    # Max number of requests that can be made per second for reqmktdata = 100
    tickers_chunked = chunkTickers(tickers, 100)

    # Request price data for all symbols
    for chunk in tickers_chunked:
        for ticker in chunk:
            print('Price Data Req: ' + str(ticker))
            contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
            app.getPrice(contract)
        time.sleep(1)

    # Process Price data
    ticker_data, issue_tickers = processQueue(app.price_queue, tickers, app, q2=app.close_price_queue)
    return ticker_data, issue_tickers


'''
TODO: update with comments
'''
def getFundamentalData(app, tickers):
    # 2 req/s seem to avoid pacing errors
    tickers_chunked = chunkTickers(tickers, 2)

    # Request fundamental data
    for chunk in tickers_chunked:
        if app.slowdown:
            print('Taking 10 second nap to hoepfully fix pacing violation')
            time.sleep(10)
            app.slowdown = False
        for ticker in chunk:
            print('Fundamental Data Req: ' + str(ticker))
            contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
            app.getFinStatements(contract, "ReportsFinStatements")
        time.sleep(1)

    # Process Fundamental data
    fund_ticker_data, data_issue_tickers = processQueue(app.fundamental_data_q, tickers, app)

    # Re-request fundamental data for any tickers that gave
    # us a pacing error
    try_agains = []
    for key, val in data_issue_tickers.items():
        if 'pacing violation' in val:
            try_agains.append(key)
    if try_agains:
        print('Retrying some tickers due to pacing violations')
        tickers_chunked = chunkTickers(try_agains, 2)
        for chunk in tickers_chunked:
            if app.slowdown:
                print('Taking 10 second nap to hoepfully fix pacing violation')
                time.sleep(10)
                app.slowdown = False
            for ticker in chunk:
                print(ticker)
                contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
                app.getFinStatements(contract, "ReportsFinStatements")
            time.sleep(1)
        try_again_data, try_again_issues = processQueue(app.fundamental_data_q, try_agains, app)

        # Update our two lists
        for key, val in try_again_data.items():
            fund_ticker_data[key] = val
            del data_issue_tickers[key]
        for key, val in try_again_issues.items():
            if val != data_issue_tickers[key]:
                data_issue_tickers[key] = val
    return fund_ticker_data, data_issue_tickers


'''
TODO: update with comments
'''
def getHistData(app, tickers, duration):
    # Max number of requests that can be made per second for reqHistoricalData = 50
    # Doing 40/sec just to be safe
    tickers_chunked = chunkTickers(tickers, 40)

    # Request price data for all symbols
    for chunk in tickers_chunked:
        for ticker in chunk:
            print('Hist Data Req: ' + str(ticker))
            contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
            app.getHistoricalData(contract, duration)
        time.sleep(1)

    # Process Price data
    ticker_data, issue_tickers = processQueue(app.hist_data_q, tickers, app)
    return ticker_data, issue_tickers


"""
TODO: update with comments
"""
def chunkTickers(tickers, n):
    return [tickers[i * n:(i + 1) * n] for i in range((len(tickers) + n - 1) // n )]


def loadTickers(ticker_file):
    with open(ticker_file) as f:
        tickers = [line.rstrip('\n') for line in f]

    # Replaces '.' and '-' with a space e.g. BRK.B should be BRK B
    ticker_cp = tickers
    for i, ticker in enumerate(ticker_cp):
        if '.' in ticker and '$' not in ticker:
            tickers[i] = ticker.replace('.', ' ')
        if '-' in ticker:
            tickers[i] = ticker.replace('-', ' ')

    # Handle Foreign Stocks - currency after delimiter '$'
    tickers = [t.split('$') if '$' in t else t for t in tickers]

    return tickers


def clear(app):
    resp = input("\nAre you sure you want to clear your positions?\n" +
                 "Press 'y' to continue with selling positions or any other key to cancel\n")
    if str(resp) == 'y':
        print('Selling all Positions')
        app.sellAllPositions(SAVE_FILE)


"""
Wait for Data

    A custom loop with a timeout and some checks

    Input:
        app: TestApp connected to IB
        data: str denoting which data to wait for worker thread to update
            'price': app.contract_price
            'portfolio': app.positions_df
            'orders': app.orders_df
            'hist': app.hist_data_df
            'fundamental': app.fundamental_data
            'contract': app.contract_details_flag
        timeout: How long to wait for the data before giving up

    Output: Int
        -2: Data Error
        -1: App has been disconnected
        0: Data is ready
        1: Reached timeout
"""
def waitForData(app, data, timeout=5):
    start = time.time()
    while True:
        if data == 'price':
            app_data = app.contract_price
        elif data == 'portfolio':
            app_data = app.positions_df
        elif data == 'orders':
            app_data = app.orders_df
        elif data == 'hist':
            app_data = app.hist_data_df
        elif data == 'fundamental':
            app_data = app.fundamental_data
        elif data == 'contract':
            app_data = app.contract_details_flag
        elif data == 'debt2equity':
            app_data = app.debt2equity

        if app_data is not None:
            return 0
        if time.time()-start > timeout:
            print('TIMEOUT: waiting for data')
            return 1
        if app.disconnected:
            print("DISCONNECTED")
            # Check for thread errors
            if not app.thread_errors_q.empty():
                exception = app.thread_errors_q.get()
                print('THREAD EXCEPTION:')
                print(exception)
            return -1
        # if app.data_errors:
        #     return -2


def main(args):
    app = ib.TestApp("127.0.0.1", args.port, clientId=1)
    print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                  app.twsConnectionTime()))
    waitForData(app, 'portfolio')
    print('POSITIONS:')
    print(app.positions_df)

    waitForData(app, 'orders')
    print('ORDERS:')
    print(app.orders_df)

    start = time.time()

    if args.clear:
        clear(app)

    tickers = None
    if args.input:
        tickers = loadTickers(args.input)
    elif args.ticker:
        tickers = [args.ticker]

    if args.moving_avg:
        print('Performing Moving Avg Cross')
        movingAvgCross(app, tickers, args.start, args.buy)
        print("Completed MA Cross Daily Calculations")

    if args.factor:
        print('Factor Sort')
        factorSort(app, tickers, args.rank, args.input)
        print('Factor Sort Completed')

    if args.futures:
        amt = 1
        order = ib.Order()
        order.action = "BUY"
        order.orderType = "MKT"
        order.totalQuantity = amt
        app.place_order(ContractSamples.GasFuture(), order)
        time.sleep(5)

    if args.warrants:
        print('Warrant Valuation')
        warrants(app, tickers, args.warrants_out)
        print('Warrant Valuation Completed')

    if args.ratios:
        print('Calculating Ratios')
        ratios(app, tickers)
        print('Calculating Ratios Completed')

    if args.factor_alpha:
        print('Performing Alpha within Factors')
        alphaInFactors(app, tickers, args.input)
        print('Alpha within Factors Completed')

    if args.test:
        '''
        Temporary Option to help debug/test the API
        '''
        # tickers = tickers[:300]
        data, err = getHistData(app, tickers, "6 M")
        print(len(data))
        print(err)


    print("Time")
    print(time.time()-start)
    print('Shutting down!')
    app.disconnect()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    # Functions
    parser.add_argument('--clear', help='Clear Positions (save positions from "save_from_sell.txt" file)', action='store_true')
    parser.add_argument('--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('--factor', help='Factors', action='store_true')
    parser.add_argument('--ratios', help='Calculate Ratios for all tickers', action='store_true')
    parser.add_argument('--warrants', help='Warrants Valuation', action='store_true')
    parser.add_argument('--futures', help='',action='store_true')
    parser.add_argument('--factor_alpha', help='Alpha within Factors',action='store_true')
    # Options
    parser.add_argument('-i', '--input', help='Input File of Tickers', default=None)
    parser.add_argument('-s', '--start', help='Ticker to start from (for Moving Avg Cross)', default=None)
    parser.add_argument('-r', '--rank', help='Rank Factors (for Factor)', action='store_true')
    parser.add_argument('-p', '--port', help='Port of TWS (default=7497)', default=7497, type=int)
    parser.add_argument('-t', '--ticker', help='Underlying Ticker for warrant valuation', default=None)
    parser.add_argument('-o', '--warrants_out', help='Number of warrants outstanding (in millions)', default=None, type=float)
    parser.add_argument('--buy', help='Actually Buy/Sell for an alorithm, instead of a dry run', action='store_true')
    parser.add_argument('--test', action='store_true')
    main(parser.parse_args())



# TODO
'''
- Current:
    - DCF impl
    - Backtester
        - follow logic of open sourced one
        - Only do if we can get sufficient data to use
    - tests
    - Reorg IB code to match the ib_threaded gist
        - https://gist.github.com/erdewit/0c01c754defe7cca129b949600be2e52
    - WWOWS - incorporate accounting ratios, earnings quality composite, value factor composites
        - Instead of shorting the bottom deciles, do put options?
    - Everything should be bulletproof i.e. no mid run crashes - handle errors, retry/sleep when necessary, bad ticker list
    - Move positions and orders to command line option
    - Add to README how long sp500 takes for each alpha in factors (and other algos if applicable)
        - Explain reqfundamentaldata takes up lots of time (2 req/s)
    - Remove cache data functionality. Have option to save dataframe as pickle output but thats it.
    - Better organize Ratios and Algorithm files. E.g. calcNOA should be in same file as calcP_E
        - Also give the files better names - fundamental calculations
        - Create IB folder which contains IB.py, coaCodes, contractSamples, etc


- Enhancements
    - use more threads
    - Include example outputs in README usage section
    - set stop loss mechanism
    - setup limit orders
    - argparse make certain options dependant on others
    - each algo should keep track of its own positions
        - when order placed and successfully executed, save to file or sqllite db
          so when we sell, we know how many to sell and multiple algo's don't get
          mixed up
    - Set up sql lite db to store fundamental data?
        - Need to update every 3 months and gets over 60 request per min limit
    - Hook in tableu or kibana for data visualizations
    - Set up on Jupyter? Only challenge might be dealing with IB
    - Add code layout, explanation to README


- Possible Strategies:
        (https://www.investopedia.com/articles/active-trading/101014/basics-algorithmic-trading-concepts-and-examples.asp)
    - Arbitrage
        - OTC stocks tough since don't have foreign mkt data subscriptions
    - ML
        - not on stock data but rather on the market participants (e.g. volume, ask/bid spread)
        - weighting different factors in a multi-factor model - instead of linear weighting, could use
          non-linear relationships from ML
    - Taleb strategies? Barbell, etc
    - Put-call parity (https://www.investopedia.com/articles/optioninvestor/05/011905.asp)
    - long dated option switch - when a later date option becomes a better deal automatically buy it
      and sell the one expiring sooner, valued by BS
    - Relative valuation screener
        - Use screener to find similar companies to do a relative valuation on. Something similar to Aswath's
          videos of finding mismatches i.e. ROE over the median but book value under the median would be cheap.
          Can apply to all the various multiples and their drivers
    - Ideas from TWS API group: https://groups.io/g/twsapi/topics
        - https://groups.io/g/twsapi/topic/can_algorithmic_trading_be/28672441

- Notes
    - Collapse all: ctrl-k ctrl-0, open all: ctrl-k ctrl-j
    - Ctrl-Alt-R resets the account server connection
    - Ctrl-Alt-F resets the market data connections
'''
