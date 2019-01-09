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
from Ratios import Ratio
from ContractSamples import ContractSamples
from Black_Scholes import BlackScholes


# Constants
SAVE_FILE = 'save_from_sell.txt'



"""
Alpha within Factors
"""
def alphaInFactors(app, tickers, input_f):
    start = time.time()
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    # Remove me later!
    # tickers = tickers[:100]

    # tickers, df_cache = loadCacheData(tickers, input_f, 'alpha_in_factor')

    ticker_data = {}
    issue_tickers = {}
    prices = []
    mkt_caps = []
    enterprise_vals = []
    dividends = []
    p_es = []
    ev_ebitdas = []
    ev_ss = []
    ev_fcfs = []
    noas = []
    eps = []
    debt_to_equities = []

    # Max number of requests that can be made per second for reqmktdata = 100
    tickers_chunked = chunkTickers(tickers, 100)

    # Request price data for all symbols
    for chunk in tickers_chunked:
        for ticker in chunk:
            print(ticker)
            contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
            app.getPrice(contract)
        time.sleep(1)

    # Process Price data
    ticker_data, issue_tickers = processQueue(app.price_queue, tickers, app, q2=app.close_price_queue)

    # Request fundamental data
    tickers_chunked = chunkTickers(tickers, 2)
    for chunk in tickers_chunked:
        if app.slowdown:
            print('Taking 10 second nap to hoepfully fix pacing violation')
            time.sleep(10)
            app.slowdown = False
        for ticker in chunk:
            print(ticker)
            # Get data
            contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
            app.getFinancialData(contract, "ReportsFinStatements")
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
                app.getFinancialData(contract, "ReportsFinStatements")
            time.sleep(1)
        try_again_data, try_again_issues = processQueue(app.fundamental_data_q, try_agains, app)

        # Update our two lists
        for key, val in try_again_data.items():
            fund_ticker_data[key] = val
            del data_issue_tickers[key]
        for key, val in try_again_issues.items():
            if val != data_issue_tickers[key]:
                data_issue_tickers[key] = val

    # Create our dataframe with price and fundamental data
    symbols = []
    prices = []
    datas = []
    for key, val in ticker_data.items():
        symbols.append(key)
        prices.append(ticker_data[key])
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
        latest_val, prev_val = app.parseFinancials(row['Data'])
        if qtr1:
            try:
                df.at[i, 'Dividend'] = qtr1['dividend'] + qtr2['dividend']
            except:
                pass

            # TODO: get rid of ratio class
            ratio = Ratio()

            # Numerators
            df.at[i, 'Market Cap'],  _firm_val, ev = ratio.getCompanyValues(row['Price'], qtr1)
            df.at[i, 'Enterprise Value'] = ev

            # TODO: better fix when missing quarterly reports
            # P/E
            try:
                df.at[i, 'P/E'] = ratio.getP_E(row['Price'], qtr1, qtr2, qtr3, qtr4)
            except KeyError:
                df.at[i, 'P/E'] = "N/A"

            # EV/EBITDA
            try:
                df.at[i, 'EV/EBITDA'] = ratio.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)
            except KeyError:
                df.at[i, 'EV/EBITDA'] = "N/A"

            # EV/S
            try:
                df.at[i, 'EV/S']  = ratio.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)
            except KeyError:
                df.at[i, 'EV/S']  = "N/A"

            # EV/FCF
            # TODO: better FCF calculation (see Ratios comments)
            try:
                df.at[i, 'EV/FCF']  = ratio.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)
            except KeyError:
                df.at[i, 'EV/FCF']  = "N/A"

            # Change in Net Operating Assets (1yr) - Earnings Quality
            noa = algo.calcNOA(latest_val)
            noa_prev = algo.calcNOA(prev_val)
            if noa is None or noa_prev is None:
                df.at[i, 'Change in NOA'] = "Error"
            else:
                df.at[i, 'Change in NOA'] = (noa - noa_prev)/noa_prev

            # Earnings Growth (1yr)
            if latest_val and prev_val:
                df.at[i, 'EPS Growth'] = (latest_val['eps'] - prev_val['eps'])/abs(prev_val['eps'])
            else:
                df.at[i, 'EPS Growth'] = "Error"

            # Leverage
            df.at[i, 'Debt to Equity'] = algo.calcDebtToEquity(qtr1)

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
    # Calculating momentum here
    for i, row in df.iterrows():
        # Momentum - trailing 6 months return
        contract = app.createContract(row['Symbol'], "STK", "USD", "SMART", "ISLAND")
        # TODO: Batch request this - fix how we store hist data
        app.getHistoricalData(contract, "6 M")
        waitForData(app, 'hist')
        df.at[i, 'Momentum'] = algo.calcTotalReturn(app.hist_data_df.iloc[0]['price'], row['Price'], row['Dividend'])
        app.resetData()

    # Sort and Remove Bottom Deciles
    columns = ['Momentum', 'Debt to Equity', 'EPS Growth', 'Change in NOA']
    for column in columns:
        if df[column].dtype == 'object':
            df = df[df[column] != 'Error']
        if column == 'Momentum' or column == 'EPS Growth':
            df = df.sort_values(column, ascending=False)
        else:
            df = df.sort_values(column)
        cutoff = int(df.shape[0]/10)
        if cutoff == 0:
            cutoff = 1
        df = df[:-cutoff]


    df = df.sort_values('Value Score', ascending=False)
    df = df.reset_index(drop=True,)
    print('Final Results:')
    print(df)


    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)
    print("Time")
    print(time.time()-start)
    return


"""
Ratio Calculator
    - smooth out, add comments, proof read, README usage and algo sections, etc
    - multithread mkt data and fundamental data requests (10 threads)
    - Sketchy Accounting detection: Use Beneish's M-Score or Montier's C-Score (see gmtresearch.com)
    - Bankruptcy Risk: Altman Z-Score
    - Create a final row in dataframe for averages
    - Use WWOWS cash flow definitions (or GuruFocus):
        (cash flow = net income + depreciation + non cash expenses,
         fcf = cash flow - capex - dividends(including prefered))
"""
def ratios(app, tickers):
    mkt_caps = []
    firm_vals = []
    enterprise_vals = []
    p_es = []
    ev_ebitdas = []
    p_bvs = []
    ev_ss = []
    ev_fcfs = []
    # tickers = tickers[14:]
    for ticker in tickers:
        print(ticker)

        # Handle Foreign Stocks
        if '$' in ticker:
            ticker, currency = ticker.split('$')
            contract = app.createContract(ticker, "STK", currency, "SMART")
        else:
            contract = app.createContract(ticker, "STK", "USD", "SMART")

        # Get data
        app.getPrice(contract)
        waitForData(app, 'price')
        app.getFinancialData(contract, "ReportsFinStatements")
        waitForData(app, 'fundamental')
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(app.fundamental_data, quarterly=True)
        ratio = Ratio()

        # Numerators
        mkt_cap, firm_val, ev = ratio.getCompanyValues(app.contract_price, qtr1)

        # P/E
        p_e = ratio.getP_E(app.contract_price, qtr1, qtr2, qtr3, qtr4)

        # EV/EBITDA
        ev_ebitda = ratio.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)

        # P/B
        p_b = ratio.getP_B(app.contract_price, qtr1)

        # EV/S
        ev_s = ratio.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)

        # EV/FCF
        ev_fcf = ratio.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)

        mkt_caps.append(mkt_cap)
        firm_vals.append(firm_val)
        enterprise_vals.append(ev)
        p_es.append(p_e)
        ev_ebitdas.append(ev_ebitda)
        p_bvs.append(p_b)
        ev_ss.append(ev_s)
        ev_fcfs.append(ev_fcf)
        app.resetData()

    data = {'Symbol': tickers, 'Market Cap': mkt_caps, 'Firm Value': firm_vals,
            'Enterprise Value': enterprise_vals, 'P/E': p_es, 'EV/EBITDA': ev_ebitdas,
            'P/B': p_bvs, 'EV/S': ev_ss, 'EV/FCF': ev_fcfs}
    df = pandas.DataFrame(data=data)
    print(df)


"""
BS warrants
    - any todos from old repo?
    - add readme to this repo readme
    - proper tests
    - Use yield of T-bill closest to expiry date as risk value
"""
def warrants(app, ticker, warrants_out):
    if ticker is None:
        print('Error: Must provide ticker for warrant valuation')
        return

    if warrants_out is None:
        print('Number of warrants outstanding was not provided. Will not calculate with share dilution.')

    # Take user input for vol?
    vols = [.2, .3, .35, .4, .5, .6]
    data = {'Volatility': vols}

    # find the warrant
    app.get_contract_details(ticker, "WAR", exchange='SMART', currency='USD')

    waitForData(app, 'contract')

    # get underlying price and div yield
    contract = app.createContract(ticker, "STK", "USD", "SMART")
    app.getPrice(contract)
    app.getFinancialData(contract, "ReportsFinStatements")

    waitForData(app, 'price')
    underlying_price = float(app.contract_price)
    div = app.contract_yield

    # get share count
    waitForData(app, 'fundamental')
    latest_val, _prev_val = app.parseFinancials(app.fundamental_data, quarterly=True)
    shares_out = latest_val['shares']

    for c in app.contract_details:
        contract = c.contract
        strike = contract.strike
        right = contract.right
        warrants_per_share = (1/float(contract.multiplier))
        expiry = datetime.datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d').strftime('%m-%d-%Y')

        # Get this from t-bill near expiry date?
        risk = .03


        prices = []
        for vol in vols:
            print(strike, app.contract_price, risk, vol,
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


"""
Factors
    - proof read code and add comments
    - try using quarterly reports? Depends on when we would rebalance?
    - finish going through microcap list?
    - ROIC Calculation
        - Stronger NIBCL calculation to include everything neccessary
        - excess cash -> dynamic required cash value. If operating losses,
          then require 5% of sales. If large operating profits, then require 1 to 2%.
        - http://news.morningstar.com/classroom2/course.asp?docId=145095&page=9
        - Aimia ROIC calc example:
            - https://www.aimia.com/wp-content/uploads/2018/11/Aimia_Q3-2018-Highlights-FINAL.pdf
"""
def factorSort(app, tickers, end, rank, input_f):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    if end and end < len(tickers):
        tickers = tickers[0:end]

    if input_f:
        tickers, df_cache = loadCacheData(tickers, input_f, 'factors')

    noas = []
    debts = []
    roics = []
    debt_to_equities = []

    factors = Factors()

    for ticker in tickers:
        print("Ticker: " + str(ticker))

        # Initate requests for data
        if '$' in ticker:
            ticker, currency = ticker.split('$')
            contract = app.createContract(ticker, "STK", currency, "SMART")
        else:
            contract = app.createContract(ticker, "STK", "USD", "SMART")
        app.getFinancialData(contract, "ReportsFinStatements")

        waitForData(app, 'fundamental')

        latest_val, prev_val = app.parseFinancials(app.fundamental_data)
        if latest_val is None:
            change_noa = "Error"
            debt_change = "Error"
            roic = "Error"
            debt2equity = "Error"
        else:
            # Net Operating Assets
            noa = algo.calcNOA(latest_val)
            noa_prev = algo.calcNOA(prev_val)
            if noa is None or noa_prev is None:
                change_noa = "Error"
            else:
                change_noa = (noa - noa_prev)/noa_prev

            # 1 year debt change
            if 'total_debt' in latest_val and 'total_debt' in prev_val:
                debt_change = algo.calcDebtChange(latest_val['total_debt'], prev_val['total_debt'])
            else:
                debt_change = "Error"

            # ROIC
            roic = algo.calcROIC(latest_val)
            if roic is None:
                roic = "Error"

            # Debt to Equity Ratio
            debt2equity = algo.calcDebtToEquity(latest_val)
            if debt2equity is None:
                debt2equity = "Error"

        # Append values to lists which we will insert into our dataframe
        debt_to_equities.append(debt2equity)
        noas.append(change_noa)
        debts.append(debt_change)
        roics.append(roic)
        app.resetData()

    data = {'symbol': tickers, 'noa_change': noas, 'debt_change': debts,
            'debt_to_equity': debt_to_equities, 'ROIC': roics}
    df = pandas.DataFrame(data=data)

    if df_cache.empty:
        print(df)
    else:
        frames = [df_cache, df]
        df = pandas.concat(frames)
        df.reset_index(drop=True, inplace=True)
        print(df)

    if input_f:
        cacheData(df, input_f, 'factors')

    if rank:
        print('Ranked Results - Top Decile for each Factor:')

        # debt to equity
        df = df[df.debt_to_equity != 'Error']
        df = df.sort_values('debt_to_equity')
        cutoff = int(df.shape[0]/10)
        df = df[:-cutoff]

        # 1yr debt change
        df = df[df.debt_change != 'Divide by Zero']
        df = df.sort_values('debt_change')
        cutoff = int(df.shape[0]/10)
        df = df[:-cutoff]

        # NOA
        df = df[df.noa_change != 'Error']
        df = df.sort_values('noa_change')
        cutoff = int(df.shape[0]/10)
        df = df[:-cutoff]

        # ROIC
        df = df[df.ROIC != 'Error']
        df = df.sort_values('ROIC', ascending=False)
        cutoff = int(df.shape[0]/10)
        df = df[:-cutoff]

        # Getting AVG
        df['debt_to_equity'] = pandas.to_numeric(df['debt_to_equity'])  # Needed to convert 0's to floats
        df.loc[-1] = ['Averages', df['noa_change'].mean(), df['debt_change'].mean(), df['debt_to_equity'].mean(), df['ROIC'].mean()]
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
Load Cache Data

    Useful for long lists of tickers. Since TWS API imposes limits on certain
    requests, it can be helpful to do smaller runs and cache results from
    previous runs so we don't need to query the API again. One should delete
    the cached data file after a couple days as the data gets stale
"""
def loadCacheData(tickers, input_f, algo):
    results_file = input_f + '.pickle.' + algo
    df_cache = pandas.DataFrame()
    previous_results_file = pathlib.Path(results_file)
    if previous_results_file.is_file():
        df_cache = pandas.read_pickle(results_file)
        tickers_to_skip = df_cache['Symbol'].tolist()
        tickers = [x for x in tickers if x not in tickers_to_skip]
    return tickers, df_cache


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
            if (len(data_map) + len(issues) == len(tickers)):
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
        factorSort(app, tickers, args.end, args.rank, args.input)
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
        warrants(app, args.ticker, args.warrants_out)
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
        contract = app.createContract('AAPL', "STK", "USD", "SMART", "ISLAND")
        # app.getPrice(contract)
        # waitForData(app, 'price')
        # print(app.contract_price)

        # app.getFinancialData(contract, "ReportsFinStatements")
        # waitForData(app, 'fundamental')
        # qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(app.fundamental_data, quarterly=True)

        # app.getHistoricalData(contract, "6 M")
        # waitForData(app, 'hist')
        # print(app.hist_data_df.iloc[0]['price'])
        symbols = ['a', 'b', 'c']
        prices = [1, 2, 3]
        datas = ['z', 'y', 'x']
        data = {'Symbol': symbols, 'Price': prices, 'Data': datas, 'Market Cap': None, 'Enterprise Value': None,
        'Dividend': None, 'Change in NOA': None, 'EPS Growth': None,'P/E': None, 'EV/EBITDA': None,
        'EV/S': None, 'EV/FCF': None, 'Debt to Equity': None}
        df = pandas.DataFrame(data)
        print(df)


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
    parser.add_argument('-e', '--end', help='Index of last ticker to process. Useful for ' +
                                            'large number of tickers (for Factor)', default=None, type=int)
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
    - Speed up fundamental data request for quicker factor sort/alpha within factor
        - Need a dict of reqId and its corresponding fundamental data for multithreaded approach
    - DCF impl
    - Backtester
        - follow logic of open sourced one
        - Only do if we can get sufficient data to use
    - tests
    - Reorg IB code to match the ib_threaded gist
        - https://gist.github.com/erdewit/0c01c754defe7cca129b949600be2e52
    - WWOWS - incorporate accounting ratios, earnings quality composite, value factor composites
        - Instead of shorting the bottom deciles, do put options?
    - Turn algo/functions into their own class? I.e. class Alpha_in_Factor()
    - Everything should be bulletproof i.e. no mid run crashes - handle errors, retry/sleep when necessary, bad ticker list
    - Move positions and orders to command line option
    - Add to README how long sp500 takes for each alpha in factors (and other algos if applicable)
        - Explain reqfundamentaldata takes up lots of time
    - Remove cache data functionality. Have option to save dataframe as pickle output but thats it


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
    - More elegant parseFinancials function
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
