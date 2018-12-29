import argparse
import datetime
import pathlib
import sys
import time
import xml.etree.ElementTree as ET

import pandas

import InteractiveBrokers as ib
import Algorithms as algo
from Algorithms import Factors
from Ratios import Ratio
from ContractSamples import ContractSamples
from Black_Scholes import BlackScholes

# Constants

SAVE_FILE = 'save_from_sell.txt'

# MA Cross
ISSUE_TICKERS = []


"""
Alpha within Factors
    - better FCF calculation (see Ratios comments)
    2) Remove value traps: Remove the bottom decile for each scoring:
        - Momentum: trailing 6-months total return (higher is better)
        - Growth: trailing change in earnings (higher is better)
        - Earnings quality: measure of accruals (lower is better), Using change in NOA since we have it,
            could also use acruals-to-assets.
        - Financial Strength: measure of leverage (lower is better), debt to equity and/or change in debt?
    3) Select the best
        - Select the top half, equally weighted.
    Run on SP500? Would rebalance once a year. Could try in different spaces i.e. microcap where factors are
    more pronounced.
"""
def alphaInFactors(app, tickers, input_f):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    # Remove me later!
    tickers = tickers[:20]

    tickers, df_cache = loadCacheData(tickers, input_f, 'alpha_in_factor')

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
    factors = Factors()


    for ticker in tickers:
        print(ticker)
        # Get data
        contract = app.createContract(ticker, "STK", "USD", "SMART", "ISLAND")
        # Need to use BRK.A instead of B for data
        if contract.symbol == 'BRK B':
            contract.symbol = 'BRK A'
        app.getPrice(contract)
        waitForData(app, 'price')
        contract_price = app.contract_price
        app.getFinancialData(contract, "ReportsFinStatements")
        waitForData(app, 'fundamental')
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(app.fundamental_data, quarterly=True)
        # Getting annual reports also
        latest_val, prev_val = app.parseFinancials(app.fundamental_data)

        # Get last two qtrs dividends
        div = qtr1['dividend'] + qtr2['dividend']

        ratio = Ratio()

        # Numerators
        mkt_cap, _firm_val, ev = ratio.getCompanyValues(contract_price, qtr1)

        # P/E
        p_e = ratio.getP_E(contract_price, qtr1, qtr2, qtr3, qtr4)

        # EV/EBITDA
        ev_ebitda = ratio.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)

        # EV/S
        ev_s = ratio.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)

        # EV/FCF
        ev_fcf = ratio.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)

        # Change in Net Operating Assets (1yr) - Earnings Quality
        noa = factors.calcNOA(latest_val)
        noa_prev = factors.calcNOA(prev_val)
        if noa is None or noa_prev is None:
            change_noa = "Error"
        else:
            change_noa = (noa - noa_prev)/noa_prev

        # Earnings Growth (1yr)
        eps_change = (latest_val['eps'] - prev_val['eps'])/prev_val['eps']

        # Leverage
        debt_to_equity = factors.calcDebtToEquity(qtr1)

        mkt_caps.append(mkt_cap)
        enterprise_vals.append(ev)
        p_es.append(p_e)
        ev_ebitdas.append(ev_ebitda)
        ev_ss.append(ev_s)
        ev_fcfs.append(ev_fcf)
        noas.append(change_noa)
        prices.append(app.contract_price)
        dividends.append(div)
        eps.append(eps_change)
        debt_to_equities.append(debt_to_equity)
        app.resetData()

    data = {'Symbol': tickers, 'Price': prices, 'Market Cap': mkt_caps, 'Enterprise Value': enterprise_vals,
            'Dividend': dividends, 'Change in NOA': noas, 'EPS Growth': eps,'P/E': p_es, 'EV/EBITDA': ev_ebitdas,
            'EV/S': ev_ss, 'EV/FCF': ev_fcfs, 'Debt to Equity': debt_to_equities}
    df = pandas.DataFrame(data=data)

    if df_cache.empty:
        print(df)
    else:
        frames = [df_cache, df]
        df = pandas.concat(frames)
        df.reset_index(drop=True, inplace=True)
        print(df)
    cacheData(df, input_f, 'alpha_in_factor')

    df = algo.compositeValueRank(df)
    print('All stocks ranked by value score:')
    print(df)
    cutoff = int(df.shape[0]*4/5)
    df = df[:-cutoff]
    df = df.reset_index(drop=True,)
    print('Top quintile of value score:')
    print(df)

    # Value Traps
    df['Momentum'] = None
    df['Debt to Equity'] = None
    # Growth and Earnings quality calculated above

    for i, row in df.iterrows():
        # Momentum - trailing 6 months return
        contract = app.createContract(row['Symbol'], "STK", "USD", "SMART", "ISLAND")
        app.get_historical_data(contract, "6 M")
        waitForData(app, 'hist')
        df.at[i, 'Momentum'] = algo.calcTotalReturn(app.hist_data_df.iloc[0]['price'], row['Price'], row['Dividend'])

        # Leverage
        # Already calculated debt to equity before ranking

        #

        app.resetData()


    print(df)


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
            noa = factors.calcNOA(latest_val)
            noa_prev = factors.calcNOA(prev_val)
            if noa is None or noa_prev is None:
                change_noa = "Error"
            else:
                change_noa = (noa - noa_prev)/noa_prev

            # 1 year debt change
            if 'total_debt' in latest_val and 'total_debt' in prev_val:
                debt_change = factors.calcDebtChange(latest_val['total_debt'], prev_val['total_debt'])
            else:
                debt_change = "Error"

            # ROIC
            roic = factors.calcROIC(latest_val)
            if roic is None:
                roic = "Error"

            # Debt to Equity Ratio
            debt2equity = factors.calcDebtToEquity(latest_val)
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
        df = df[df.noa_change != 'Error']
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
    if ISSUE_TICKERS:
        tickers = [x for x in tickers if x not in ISSUE_TICKERS]

    contract = app.createContract(None, "STK", "USD", "SMART", "ISLAND")

    for ticker in tickers:
        contract.symbol = ticker

        # Only process if no open orders with this ticker
        if app.orders_df.empty or not app.orders_df['symbol'].str.contains(ticker).any():
            app.get_historical_data(contract, "1 Y")

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
        contract = app.createContract('F', "STK", "USD", "SMART", "ISLAND")
        app.getPrice(contract)
        waitForData(app, 'price')
        print(app.contract_price)

        app.getFinancialData(contract, "ReportsFinStatements")
        waitForData(app, 'fundamental')
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(app.fundamental_data, quarterly=True)

        app.get_historical_data(contract, "6 M")
        waitForData(app, 'hist')
        print(app.hist_data_df.iloc[0]['price'])
        totalReturn = algo.calcTotalReturn(app.hist_data_df.iloc[0]['price'], app.contract_price, qtr1['dividend']+qtr2['dividend'])
        print(totalReturn)


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
    - Use fundamental data to calc debt/equity myself, remove getMktData() calls
    - WWOWS - incorporate accounting ratios, earnings quality composite, value factor composites
        - Instead of shorting the bottom deciles, do put options?


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
    - Make classes into normal functions if not using member vars i.e. Factors()
    - Set up sql lite db to store fundamental data?
        - Need to update every 3 months and gets over 60 request per min limit
    - Hook in tableu or kibana for data visualizations


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
