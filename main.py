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

from ContractSamples import ContractSamples
from Black_Scholes import BlackScholes

# Constants

SAVE_FILE = 'save_from_sell.txt'

# MA Cross
ISSUE_TICKERS = ['PX',]



def multiples(app, tickers):
    mkt_caps = []
    firm_vals = []
    enterprise_vals = []
    p_es = []
    ev_ebitdas = []
    p_bvs = []
    ev_ss = []
    tickers = tickers[:9]
    for ticker in tickers:
        contract = app.createContract(ticker, "STK", "USD", "SMART")
        app.getMktData(contract)
        while app.contract_price is None:
            print("Waiting on Mkt data")
            time.sleep(1)
        app.getFinancialData(contract, "ReportsFinStatements")
        while app.fundamental_data is None:
            print("Waiting on fundamental data")
            time.sleep(1)
        qtr1, qtr2, qtr3, qtr4 = app.parseFinancials(app.fundamental_data, quarterly=True, ttm=True)
        # Numerators
        mkt_cap = float(qtr1['shares']) * float(app.contract_price)
        firm_val = mkt_cap + qtr1['total_debt']
        if 'cash_investments' in qtr1:
            ev = firm_val - qtr1['cash_investments']
        else:
            ev = firm_val - qtr1['cash']

        # P/E
        ttm_eps = qtr1['eps'] + qtr2['eps'] + qtr3['eps'] + qtr4['eps']
        if ttm_eps <= 0:
            p_e = 'No Earnings'
        else:
            p_e = float(app.contract_price)/ttm_eps

        # EV/EBITDA
        ebitda = qtr1['op_income'] + qtr1['dep_amor'] + qtr2['op_income'] + qtr2['dep_amor'] + qtr3['op_income'] + qtr3['dep_amor'] + qtr4['op_income'] + qtr4['dep_amor']
        if ebitda <= 0:
            ev_ebitda = 'Negative EBITDA'
        else:
            ev_ebitda = ev / ebitda

        # P/B
        bv = qtr1['total_equity']
        if 'redeemable_preferred' in qtr1:
            bv = bv - qtr1['redeemable_preferred']
        if 'preferred' in qtr1:
            bv = bv - qtr1['preferred']
        bv_per_share = bv/float(qtr1['shares'])
        p_b = float(app.contract_price)/bv_per_share

        # EV/S
        ttm_rev = qtr1['revenue'] + qtr2['revenue'] + qtr3['revenue'] + qtr4['revenue']
        if ttm_rev <= 0:
            ev_s = 'No Revenue'
        else:
            ev_s = ev / ttm_rev

        mkt_caps.append(mkt_cap)
        firm_vals.append(firm_val)
        enterprise_vals.append(ev)
        p_es.append(p_e)
        ev_ebitdas.append(ev_ebitda)
        p_bvs.append(p_b)
        ev_ss.append(ev_s)
        app.resetData()

    data = {'Symbol': tickers, 'Market Cap': mkt_caps, 'Firm Value': firm_vals,
            'Enterprise Value': enterprise_vals, 'P/E': p_es, 'EV/EBITDA': ev_ebitdas,
            'P/B': p_bvs, 'EV/S': ev_ss}
    df = pandas.DataFrame(data=data)
    print(df)


def warrants(app, ticker, warrants_out):
    if ticker is None:
        print('Error: Must provide ticker for warrant valuation')
        return

    ticker = ticker

    if warrants_out is None:
        print('Number of warrants outstanding was not provided. Will not calculate with share dilution.')

    # find the warrant
    app.get_contract_details(ticker, "WAR")
    while not app.contract_details_flag:
        print("Waiting on contract data")
        time.sleep(1)

    contract = app.contract_details[0].contract

    # Finding other warrrants
    # for c in app.contract_details:
    #     if c.contract.strike != contract.strike:
    #         print(c.contract.strike)

    strike = contract.strike
    right = contract.right
    warrants_per_share = (1/float(contract.multiplier))
    expiry = datetime.datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d').strftime('%m-%d-%Y')

    # get underlying price
    contract = app.createContract(ticker, "STK", "USD", "SMART")
    app.getMktData(contract)
    app.getFinancialData(contract, "ReportsFinStatements")

    while app.contract_price is None:
        print('Waiting for mkt data')
        time.sleep(1)
    underlying_price = float(app.contract_price)
    div = app.contract_yield

    while app.fundamental_data is None:
        print("Waiting on fundamental data")
        time.sleep(1)
    latest_val, _prev_val = app.parseFinancials(app.fundamental_data, quarterly=True)
    shares_out = latest_val['shares']

    # Get this from t-bill?
    risk = .03


    # Get implied vol? Or do a range of vol values? Or take user input for vol?
    vols = [.2, .3, .35, .4, .5, .6]
    prices = []
    for vol in vols:
        print(strike, app.contract_price, risk, vol,
                        expiry, div, shares_out, warrants_out,
                        warrants_per_share)
        bs = BlackScholes(strike, underlying_price, risk, vol,
                        expiry, div, shares_out, warrants_out,
                        warrants_per_share)
        prices.append('$' + str(round(bs.price_euro_call(), 5)))
    data = {'Volatility': vols, 'Fair Price': prices}
    df = pandas.DataFrame(data=data)
    print(df)


def factorSort(app, tickers, end, rank, input):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    results_file = input + '.pickle'

    if end and end < len(tickers):
        tickers = tickers[0:end]

    df_old = pandas.DataFrame()
    previous_results_file = pathlib.Path(input + '.pickle')
    if previous_results_file.is_file():
        df_old = pandas.read_pickle(results_file)
        tickers_to_skip = df_old['symbol'].tolist()
        tickers = [x for x in tickers if x not in tickers_to_skip]

    noas = []
    debts = []
    roics = []
    debt_to_equities = []

    factors = Factors()

    for ticker in tickers:
        print("Ticker: " + str(ticker))

        # Initate requests for data
        if type(ticker) is list:
            contract = app.createContract(ticker[0], "STK", ticker[2], ticker[1])
        else:
            contract = app.createContract(ticker, "STK", "USD", "SMART")
        app.getFinancialData(contract, "ReportsFinStatements")
        app.getMktData(contract)

        while app.fundamental_data is None:
            print("Waiting on fundamental data")
            time.sleep(1)

        latest_val, prev_val = app.parseFinancials(app.fundamental_data)
        if latest_val is None:
            change_noa = "Error"
            debt_change = "Error"
            roic = "Error"
            app.debt2equity = "Error"
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
            while app.debt2equity is None:
                print('Waiting on ratio data')
                time.sleep(1)

        # Append values to lists which we will insert into our dataframe
        debt_to_equities.append(app.debt2equity)
        noas.append(change_noa)
        debts.append(debt_change)
        roics.append(roic)
        app.resetData()

    data = {'symbol': tickers, 'noa_change': noas, 'debt_change': debts,
            'debt_to_equity': debt_to_equities, 'ROIC': roics}
    df = pandas.DataFrame(data=data)

    if df_old.empty:
        print(df)
    else:
        frames = [df_old, df]
        df = pandas.concat(frames)
        df.reset_index(drop=True, inplace=True)
        print(df)
    df.to_pickle(results_file)

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


def movingAvgCross(app, tickers, start):
    if tickers is None:
        print("Error: Must provide file of tickers by '-i' option")
        return

    if start is not None:
        start_index = tickers.index(start) + 1
        tickers = tickers[start_index:]
    if ISSUE_TICKERS:
        tickers = [x for x in tickers if x not in ISSUE_TICKERS]

    # contract = app.createContract(None, "STK", "USD", "SMART", "ISLAND")
    contract = app.createContract(None, "STK", "USD", "SMART")

    # Replaces '.' with a space e.g. BRK.B should be BRK B
    for ticker in tickers:
        if '.' in ticker:
            ticker = ticker.replace('.', ' ')
        contract.symbol = ticker

        # Only process if no open orders with this ticker
        if app.orders_df.empty or not app.orders_df['symbol'].str.contains(ticker).any():
            app.get_historical_data(contract)

            while app.hist_data_df is None:
                print("Waiting on historical data")
                time.sleep(1)
            print("Symbol: " + ticker)
            # Golden Cross and not in portfolio -> buy
            if algo.movingAvgCross(app.hist_data_df) and not app.portfolioCheck(ticker):
                print('Placing Buy Order for: ' + ticker)
                amt = app.calcOrderSize(float(app.hist_data_df.tail(1)['price']), 1000)
                order = ib.Order()
                order.action = "BUY"
                order.orderType = "MKT"
                order.totalQuantity = amt
                app.place_order(contract, order)
            # Death cross and in portfolio -> sell
            elif (app.portfolioCheck(ticker) and not algo.movingAvgCross(app.hist_data_df)):
                print('Placing Sell Order for: ' + ticker)
                app.sellPosition(ticker, 'STK')
            app.resetData()


def loadTickers(ticker_file):
    with open(ticker_file) as f:
            tickers = [line.rstrip('\n') for line in f]
        # Handle Foreign Stocks
        # for i, ticker in enumerate(tickers):
        #     if '-' in ticker:
        #         tickers[i] = ticker.split('-')
        # tickers[:] = [ticker.split('-') for ticker in tickers if '-' in ticker]
    return tickers


def clear(app):
    resp = input("\nAre you sure you want to clear your positions?\n" +
                 "Press 'y' to continue with selling positions or any other key to cancel\n")
    if str(resp) == 'y':
        print('Selling all Positions')
        app.sellAllPositions(SAVE_FILE)


def main(args):
    app = ib.TestApp("127.0.0.1", args.port, clientId=1)
    print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                  app.twsConnectionTime()))
    while app.positions_df is None:
        print("Waiting on Positions")
        time.sleep(1)
    print('POSITIONS:')
    print(app.positions_df)

    while app.orders_df is None:
        print("Waiting on Open Orders")
        time.sleep(1)
    print('ORDERS:')
    print(app.orders_df)

    if args.clear:
        clear(app)

    tickers = None
    if args.input:
        tickers = loadTickers(args.input)

    if args.moving_avg:
        print('Performing Moving Avg Cross')
        movingAvgCross(app, tickers, args.start)
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
        app.place_order(ContractSamples.OilFuture(), order)
        time.sleep(5)

    if args.warrants:
        print('Warrant Valuation')
        warrants(app, args.ticker, args.warrants_out)
        print('Warrant Valuation Completed')

    if args.multiples:
        print('Calculating Multiples')
        multiples(app, tickers)
        print('Calculating Multiples Completed')

    if args.test:
        contract = app.createContract('AA.', "STK", "GBP", "LSE")
        app.getFinancialData(contract, "ReportsFinStatements")
        while app.fundamental_data is None:
            print("Waiting on fundamental data")
            time.sleep(1)
        print(app.fundamental_data)


    print('Shutting down!')
    app.disconnect()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    parser.add_argument('-c', '--clear', help='Clear Positions (save positions from "save_from_sell.txt" file)', action='store_true')
    parser.add_argument('-m', '--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('-s', '--start', help='Ticker to start from', default=None)
    parser.add_argument('-f', '--factor', help='Factors', action='store_true')
    parser.add_argument('--multiples', help='Calculate Multiples for all tickers', action='store_true')
    parser.add_argument('-i', '--input', help='Input File of Tickers', default=None)
    parser.add_argument('-e', '--end', help='Index of last ticker to process. Useful for ' +
                                            'large number of tickers', default=None, type=int)
    parser.add_argument('-r', '--rank', help='Rank Factors', action='store_true')
    parser.add_argument('-p', '--port', help='Port of TWS (default=7497)', default=7497, type=int)
    parser.add_argument('--futures', help='',action='store_true')
    parser.add_argument('-w', '--warrants', help='Warrants Valuation', action='store_true')
    parser.add_argument('-t', '--ticker', help='Underlying Ticker for warrant valuation', default=None)
    parser.add_argument('-o', '--warrants_out', help='Number of warrants outstanding (in millions)', default=None, type=float)
    parser.add_argument('--test', action='store_true')
    main(parser.parse_args())



# TODO
'''
- Current:
    - Microcap
        - proof read code and add comments
        - try using quarterly reports? Depends on when we would rebalance
        - finish going through microcap list?
        - add old README to this README under algos
    - BS warrants
        - any todos from old repo?
        - add readme to this repo readme
        - proper tests
        - handle multiple warrants .e.g TDW A/B
            - Value both and display in dataframe to easily determine better deals
    - Multiple/Relative Valuation Calculator
        - smooth out, add comments, proof read, README usage and algo sections, etc
    - MA Cross
        - always gets stuck ~83rd ticker (AVGO), not ticker specific, what's the issue?
    - DCF impl
    - Backtester
        - follow logic of open sourced one
    - Add support for foreign stocks i.e. read exchange from ticker txt file
        - if '-' in ticker, then extract second part which is exchange e.g. CTT-BVL
        - Only works for fundamental data, not mktdata since no subscription
            - Use fundamental data->ReportRatios to get debt to equity?
    - tests


- Enhancements
    - setup while loop limits (e.g. 10 iterations)
        - print tickers at end that gave us an issue
        - if hit IB request limit, then wait some seconds and try again
        - smartly solve when stuck in loops
    - use more threads
    - Include example outputs in README usage section
    - set stop loss mechanism
    - setup limit orders
    - argparse make certain options dependant on others
    - each algo should keep track of its own positions
        - when order placed and successfully executed, save to file or sqllite db
          so when we sell, we know how many to sell and multiple algo's don't get
          mixed up
    - ROIC Calculation
        - Stronger NIBCL calculation to include everything neccessary
        - excess cash -> dynamic required cash value. If operating losses,
          then require 5% of sales. If large operating profits, then require 1 to 2%.
        - http://news.morningstar.com/classroom2/course.asp?docId=145095&page=9
        - Aimia ROIC calc example:
            - https://www.aimia.com/wp-content/uploads/2018/11/Aimia_Q3-2018-Highlights-FINAL.pdf


- strategies:
        (https://www.investopedia.com/articles/active-trading/101014/basics-algorithmic-trading-concepts-and-examples.asp)
    - Arbitrage
        - OTC stocks tough since don't have foreign mkt data subscriptions
    - ML
        - not on stock data but rather on the market participants (e.g. volume, ask/bid spread)
        - weighting different factors in a multi-factor model - instead of linear weighting, could use
          non-linear relationships from ML
    - Taleb strategies? Barbell, etc
    - Put-call parity (https://www.investopedia.com/articles/optioninvestor/05/011905.asp)
    - Factor-based strategy
        - Microcap
    - long dated option switch - when a later date option becomes a better deal automatically buy it
      and sell the one expiring sooner, valued by BS
    - Relative valuation screener
        - Use screener to find similar companies to do a relative valuation on. Something similar to Aswath's
          videos of finding mismatches i.e. ROE over the median but book value under the median would be cheap.
          Can apply to all the various multiples and their drivers


Implement three O'SAM articles
    - Factors: https://www.osam.com/Commentary/factors-from-scratch
    - Microcaps: https://www.osam.com/Commentary/microcaps-factor-spreads-structural-biases-and-the-institutional-imperative
    - Alpha within Factors: https://www.osam.com/Commentary/alpha-within-factors

'''