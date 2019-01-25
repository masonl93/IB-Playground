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


def alphaInFactors(app, tickers, input_f, out_f):
    """
    Alpha within Factors
    """

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
            'Dividend': None, 'Momentum': None, 'Change in NOA': None, 'EPS Growth': None, 'P/E': None, 'EV/EBITDA': None,
            'EV/S': None, 'EV/FCF': None, 'Debt to Equity': None}
    df = pandas.DataFrame(data=data).dropna(subset=['Price', 'Data'])
    print("Price Data:")
    print(df)

    # Loop through dataframe and update specific values
    for i, row in df.iterrows():
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(
            row['Data'], quarterly=True)
        # Getting annual reports also
        current_annual, prev_annual = app.parseFinancials(row['Data'])

        df.at[i, 'Dividend'] = Ratios.getDivPayout(qtr1, qtr2)

        # Numerators
        df.at[i, 'Market Cap'], ev = Ratios.getCompanyValues(row['Price'], qtr1)[
            ::2]
        df.at[i, 'Enterprise Value'] = ev

        df.at[i, 'P/E'] = Ratios.getP_E(row['Price'], qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/EBITDA'] = Ratios.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/S'] = Ratios.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/FCF'] = Ratios.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)

        df.at[i, 'Change in NOA'] = Ratios.calcChangeInNOA(
            current_annual, prev_annual)
        df.at[i, 'EPS Growth'] = Ratios.calcOneYearGrowth(
            current_annual, prev_annual)
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
    hist_data, hist_issue_tickers = getHistData(
        app, list(df['Symbol'].values), "6 M")

    # Update df with momentum values
    for i, row in df.iterrows():
        if row['Symbol'] in hist_data:
            df.at[i, 'Momentum'] = algo.calcTotalReturn(
                hist_data[row['Symbol']].iloc[0]['price'], row['Price'], row['Dividend'])
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
    if out_f:
        saveResults(df, out_f)

    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)
    print('Tickers missing historical data: (%s)' % len(hist_issue_tickers))
    print(hist_issue_tickers)
    return


def ratios(app, tickers, out_f):
    """
    Ratio Calculator
    """

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
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(
            row['Data'], quarterly=True)

        # Numerators
        df.at[i, 'Market Cap'], df.at[i, 'Firm Value'], ev = Ratios.getCompanyValues(
            row['Price'], qtr1)
        df.at[i, 'Enterprise Value'] = ev

        df.at[i, 'P/E'] = Ratios.getP_E(row['Price'], qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/EBITDA'] = Ratios.getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/S'] = Ratios.getEV_S(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'EV/FCF'] = Ratios.getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4)
        df.at[i, 'P/B'] = Ratios.getP_B(row['Price'], qtr1)

    df = df.drop(columns=['Data'])
    print('Results:')
    with pandas.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
    print(df)
    if out_f:
        saveResults(df, out_f)

    print('Tickers missing price data: (%s)' % len(issue_tickers))
    print(issue_tickers)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)
    return


def warrants(app, tickers, warrants_out):
    """
    BS warrants
        - TODO: add readme to this repo readme?
    """

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
        # Find the warrant
        contract_details = app.getContractDetails(
            key, "WAR", exchange='SMART', currency='USD')
        underlying_price = float(val)
        # Get dividend yield
        contract = app.createContract(key, "STK", "USD", "SMART", "ISLAND")
        div = app.getYield(contract)
        # Find share count from financials
        qtr1 = app.parseFinancials(fund_ticker_data[key], quarterly=True)[0]
        shares_out = qtr1['total_common_shares_outstanding']

        for c in contract_details:
            contract = c.contract
            strike = contract.strike
            # right = contract.right
            warrants_per_share = (1/float(contract.multiplier))
            expiry = datetime.datetime.strptime(
                contract.lastTradeDateOrContractMonth, '%Y%m%d').strftime('%m-%d-%Y')

            # TODO: Get this from t-bill near expiry date?
            risk = .03

            prices = []
            for vol in vols:
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


def factorSort(app, tickers, rank, input_f, out_f):
    """
    Factors
    """

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
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(
            row['Data'], quarterly=True)
        current_annual, prev_annual = app.parseFinancials(row['Data'])
        df.at[i, 'Change in NOA'] = Ratios.calcChangeInNOA(
            current_annual, prev_annual)
        df.at[i, 'Debt to Equity'] = Ratios.calcDebtToEquity(qtr1)
        df.at[i, 'ROIC'] = Ratios.calcROIC(qtr1, qtr2, qtr3, qtr4)
        df.at[i, '1yr Debt Change'] = Ratios.calcDebtChange(
            current_annual, prev_annual)

    df = df.drop(columns=['Data'])
    print(df)
    if out_f:
        saveResults(df, out_f)
    print('Tickers missing fundamental data: (%s)' % len(data_issue_tickers))
    print(data_issue_tickers)

    if rank:
        print('Ranked Results - Remove Lowest Decile for each Factor:')
        columns = ['Change in NOA', 'Debt to Equity',
                   'ROIC', '1yr Debt Change']
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
        df.loc[-1] = ['Averages', df['Change in NOA'].mean(), df['1yr Debt Change'].mean(),
                      df['Debt to Equity'].mean(), df['ROIC'].mean()]
        print(df.reset_index(drop=True,))
        if out_f:
            saveResults(df, out_f + '_ranked')


def movingAvgCross(app, positions, orders, tickers, buy):
    """
    MA Cross
    """

    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    hist_data, hist_issue_tickers = getHistData(app, tickers, "1 Y")
    for ticker in tickers:
        # Ensure we got hist data for this ticker
        if ticker not in hist_data:
            continue
        # Only process if no open orders with this ticker
        if orders.empty or not orders['symbol'].str.contains(ticker).any():
            # Golden Cross and not in portfolio -> buy
            if algo.movingAvgCross(hist_data[ticker]) and not app.portfolioCheck(ticker, positions):
                print('Placing Buy Order for: ' + ticker)
                if buy:
                    amt = app.calcOrderSize(
                        float(hist_data[ticker].tail(1)['price']), 1000)
                    contract = app.createContract(
                        ticker, "STK", "USD", "SMART", "ISLAND")
                    order = ib.Order()
                    order.action = "BUY"
                    order.orderType = "MKT"
                    order.totalQuantity = amt
                    app.place_order(contract, order)
            # Death cross and in portfolio -> sell
            elif (app.portfolioCheck(ticker, positions) and not algo.movingAvgCross(hist_data[ticker])):
                print('Placing Sell Order for: ' + ticker)
                if buy:
                    app.sellPosition(ticker, 'STK', orders, positions)

    print('Completed MA Cross Algo')
    print('Tickers missing historical data: (%s)' % len(hist_issue_tickers))
    print(hist_issue_tickers)


def saveResults(df, output_f):
    """
    Save Results

        Saves a dataframe to file in pickle format for use on a later.
    """
    df.to_pickle(output_f)


def processQueue(q, tickers, app, q2=None):
    """
    Process Queue

        Processes a data queue from IB class

        Input:
            q: the main queue to process
            tickers: list of tickers
            app: Needed to reference IB.reqId_map to link up
                a reqId to a ticker
            q2: (optional) secondary queue to process in the case
                that a ticker is missing from q. This can be useful
                for reqMktData when there are no trades today so we
                want to just use previous day close price, so use q2
    """

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


def getPriceData(app, tickers):
    '''
    Get Price Data

        Gets price data for a given list of tickers
        Tries to do max requests per sec w/o causing any errors

        Output:
            ticker_data: dict w/ tickers as keys and prices as values
            issue_tickers: dict w/ tickers as keys and errors as values
    '''
    # Max number of requests that can be made per second for reqmktdata = 100
    tickers_chunked = chunkTickers(tickers, 100)

    # Request price data for all symbols
    for chunk in tickers_chunked:
        for ticker in chunk:
            print('Price Data Req: ' + str(ticker))
            contract = app.createContract(
                ticker, "STK", "USD", "SMART", "ISLAND")
            app.getPrice(contract)
        time.sleep(1)

    # Process Price data
    ticker_data, issue_tickers = processQueue(
        app.price_queue, tickers, app, q2=app.close_price_queue)
    return ticker_data, issue_tickers


def getFundamentalData(app, tickers):
    '''
    Get Fundamental Data

        Gets fundamental data for a given list of tickers
        Tries to do max requests per sec w/o causing any errors
        If we face a pacing error, we try to slow down and attempt
        to try again since these are not real errors and can most
        of the time be resolved

        Output:
            fund_ticker_data: dict w/ tickers as keys and xml fundamental data as values
            data_issue_tickers: dict w/ tickers as keys and errors as values
    '''
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
            contract = app.createContract(
                ticker, "STK", "USD", "SMART", "ISLAND")
            app.getFinStatements(contract, "ReportsFinStatements")
        time.sleep(1)

    # Process Fundamental data
    fund_ticker_data, data_issue_tickers = processQueue(
        app.fundamental_data_q, tickers, app)

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
                contract = app.createContract(
                    ticker, "STK", "USD", "SMART", "ISLAND")
                app.getFinStatements(contract, "ReportsFinStatements")
            time.sleep(1)
        try_again_data, try_again_issues = processQueue(
            app.fundamental_data_q, try_agains, app)

        # Update our two lists
        for key, val in try_again_data.items():
            fund_ticker_data[key] = val
            del data_issue_tickers[key]
        for key, val in try_again_issues.items():
            if val != data_issue_tickers[key]:
                data_issue_tickers[key] = val
    return fund_ticker_data, data_issue_tickers


def getHistData(app, tickers, duration):
    '''
    Get Historical Data

        Gets historical data for a given list of tickers
        Tries to do max requests per sec w/o causing any errors
        Duration should match format of IB.reqHistoricalData

        Output:
            ticker_data: dict w/ tickers as keys and dataframe of hist data as values
            issue_tickers: dict w/ tickers as keys and errors as values
    '''
    # Max number of requests that can be made per second for reqHistoricalData = 50
    # Doing 40/sec just to be safe
    tickers_chunked = chunkTickers(tickers, 40)

    # Request price data for all symbols
    for chunk in tickers_chunked:
        for ticker in chunk:
            print('Hist Data Req: ' + str(ticker))
            contract = app.createContract(
                ticker, "STK", "USD", "SMART", "ISLAND")
            app.getHistoricalData(contract, duration)
        time.sleep(1)

    # Process Price data
    ticker_data, issue_tickers = processQueue(app.hist_data_q, tickers, app)
    return ticker_data, issue_tickers


def chunkTickers(tickers, n):
    """
    Chunk Tickers

        Given a list tickers, split into sublists of length n
        This is used as different IB functions can only take
        so many request per second before throwing an error
    """
    return [tickers[i * n:(i + 1) * n] for i in range((len(tickers) + n - 1) // n)]


def loadTickers(ticker_file):
    '''
    Load Tickers
    '''

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


def main(args):
    app = ib.App("127.0.0.1", args.port, clientId=1)
    print("serverVersion:%s connectionTime:%s" % (app.client.serverVersion(),
                                                  app.client.twsConnectionTime()))
    account = app.getAccounts()
    print('Accounts:', account)
    positions = app.getPositions(account)
    print('POSITIONS:')
    print(positions)

    orders = app.getOrders()
    print('ORDERS:')
    print(orders)

    start = time.time()

    tickers = None
    if args.input:
        tickers = loadTickers(args.input)
    elif args.ticker:
        tickers = [args.ticker]

    if args.moving_avg:
        print('Performing Moving Avg Cross')
        movingAvgCross(app, positions, orders, tickers, args.buy)
        print("Completed MA Cross Daily Calculations")

    if args.factor:
        print('Factor Sort')
        factorSort(app, tickers, args.rank, args.input, args.output)
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
        ratios(app, tickers, args.output)
        print('Calculating Ratios Completed')

    if args.factor_alpha:
        print('Performing Alpha within Factors')
        alphaInFactors(app, tickers, args.input, args.output)
        print('Alpha within Factors Completed')

    if args.test:
        '''
        Temporary Option to help debug/test the API
        '''
        tickers = tickers[:80]
        # for t in tickers:
        #     print(t)
        #     contract = app.createContract(t, "STK", "USD", "SMART", "ISLAND")
        #     print(app.getYield(contract))
        data, err = getPriceData(app, tickers)
        print(len(data))
        print(data['MMM'])
        print(err)

    print("Time")
    print(time.time()-start)
    print('Shutting down!')
    app.client.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    # Functions
    parser.add_argument(
        '--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('--factor', help='Factors', action='store_true')
    parser.add_argument(
        '--ratios', help='Calculate Ratios for all tickers', action='store_true')
    parser.add_argument(
        '--warrants', help='Warrants Valuation', action='store_true')
    parser.add_argument('--futures', help='', action='store_true')
    parser.add_argument(
        '--factor_alpha', help='Alpha within Factors', action='store_true')
    # Options
    parser.add_argument(
        '-i', '--input', help='Input File of Tickers', default=None)
    parser.add_argument(
        '-r', '--rank', help='Rank Factors (for Factor)', action='store_true')
    parser.add_argument(
        '-p', '--port', help='Port of TWS (default=7497)', default=7497, type=int)
    parser.add_argument(
        '-t', '--ticker', help='Underlying Ticker for warrant valuation', default=None)
    parser.add_argument('-o', '--warrants_out',
                        help='Number of warrants outstanding (in millions)', default=None, type=float)
    parser.add_argument(
        '--buy', help='Actually Buy/Sell for an alorithm, instead of a dry run', action='store_true')
    parser.add_argument('--test', action='store_true')
    parser.add_argument(
        '--output', help='Output file to save to', default=None)
    main(parser.parse_args())


# TODO
'''
- Current:
    - tests
    - Move positions and orders to command line option
    - Better organize Ratios and Algorithm files. E.g. calcNOA should be in same file as calcP_E
        - Also give the files better names - fundamental calculations
        - Create IB folder which contains IB.py, coaCodes, contractSamples, etc
        - Add code layout explanation to README
        - explain tools/ dir
    - Utilize df.rank() for value comp score?
        - Assigns P/E 100, when lowest P/E, etc


- Enhancements/Improvements
    - Include example outputs in README usage section
    - setup limit orders and set stop loss mechanism
    - argparse make certain options dependant on others
    - Hook in tableu or kibana for data visualizations
    - Set up on Jupyter? Only challenge might be dealing with IB
    - DCF impl
    - Function to sell all positions - use for reseting paper acct.
    - Backtester
        - follow logic of open sourced one
        - Only do if we can get sufficient data to use
    - WWOWS - incorporate accounting ratios, earnings quality composite, value factor composites
        - Instead of shorting the bottom deciles, do put options?
    - Ratios
        - Sketchy Accounting detection: Use Beneish's M-Score or Montier's C-Score (see gmtresearch.com)
        - Bankruptcy Risk: Altman Z-Score
        - Tobins Q, ROOIC, other scores that GW investors use
        - Create a final row in dataframe for averages
    - Warrants
        - add support for list/input file of tickers
    - Other strategies/algos
        - Arbitrage
        - ML
        - Taleb strategies
        - Ideas from TWS API group: https://groups.io/g/twsapi/topics
            - https://groups.io/g/twsapi/topic/can_algorithmic_trading_be/28672441

- Notes
    - Collapse all: ctrl-k ctrl-0, open all: ctrl-k ctrl-j
    - Ctrl-Alt-R resets the account server connection
    - Ctrl-Alt-F resets the market data connections
'''
