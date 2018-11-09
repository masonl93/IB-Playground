import argparse
import pathlib
import time
import xml.etree.ElementTree as ET

import pandas

import InteractiveBrokers as ib
import Algorithms as algo
from Algorithms import Factors


# Constants

# MA Cross
LAST_PROCESSED = 'CA'
ISSUE_TICKERS = ['PX', 'CHRW', 'BF.B', 'BR', 'AVGO']

# Microcaps
MICRO_RESULTS_F = 'microcap_results.pickle'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    parser.add_argument('-m', '--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('-o', '--other', help='Other Algo', action='store_true')
    parser.add_argument('-p', '--port', help='Port of TWS (default=7497)', default=7497, type=int)
    args = parser.parse_args()

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


    if args.moving_avg:
        print('Performing Moving Avg Cross')
        with open('sp500.txt') as f:
            tickers = [line.rstrip('\n') for line in f]
        if LAST_PROCESSED is not None:
            start_index = tickers.index(LAST_PROCESSED) + 1
            tickers = tickers[start_index:]
        if ISSUE_TICKERS:
            tickers = [x for x in tickers if x not in ISSUE_TICKERS]

        contract = app.createContract(None, "STK", "USD", "SMART", "ISLAND")

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
                    pos = app.getPosDetails(ticker, 'STK')
                    if pos.shape[0] > 1:
                        print('Multiple matching positions, defaulting to first record')
                        pos = pos.head(0)
                    order = ib.Order()
                    order.action = "SELL"
                    order.orderType = "MKT"
                    order.totalQuantity = int(pos['pos'])
                    app.place_order(contract, order)
                app.hist_data_df = None
        print("Completed MA Cross Daily Calculations")

    if args.other:
        print('Factor Sort')

        with open('microcaps.txt') as f:
            tickers = [line.rstrip('\n') for line in f]

        tickers = tickers[0:30]

        df_old = pandas.DataFrame()
        previous_results_file = pathlib.Path(MICRO_RESULTS_F)
        if previous_results_file.is_file():
            df_old = pandas.read_pickle(MICRO_RESULTS_F)
            tickers_to_skip = df_old['symbol'].tolist()
            tickers = [x for x in tickers if x not in tickers_to_skip]

        noas = []
        debts = []
        roics = []
        debt_to_equities = []

        factors = Factors()

        for ticker in tickers:
            print("Ticker: " + ticker)

            # Initate requests for data
            contract = app.createContract(ticker, "STK", "USD", "SMART")
            app.getFinancialData(contract, "ReportsFinStatements")

            while app.fundamental_data is None:
                print("Waiting on fundamental data")
                time.sleep(1)

            latest_val, prev_val = factors.parseFinancials(app.fundamental_data)
            if latest_val is None:
                change_noa = "Error"
                change_debt = "Error"
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
                    change_debt = "Error"

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
            debts.append(change_debt)
            roics.append(roic)
            app.fundamental_data = None
            app.debt2equity = None

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
        df.to_pickle(MICRO_RESULTS_F)


    print('Shutting down!')
    app.disconnect()





# TODO
'''
- Current:
    - finish microcap
        - proof read code and add comments
    - algos should be ticker agnostic. Input should be a file containing tickers
    - DCF impl
    - create backtester (follow logic of open sourced one)
    - ML project unrelated to finance and then ML algo strategy?


- Enhancements
    - setup while loop limits (e.g. 10 iterations)
        - print tickers at end that gave us an issue
    - use more threads
    - set stop loss mechanism
    - setup limit orders
    - each algo should keep track of its own positions
        - when order placed and successfully executed, save to file or sqllite db
          so when we sell, we know how many to sell and multiple algo's don't get
          mixed up
    - ROIC Calculation
        - Stronger NIBCL calculation to include everything neccessary
        - excess cash -> dynamic required cash value. If operating losses,
          then require 5% of sales. If large operating profits, then require 1 to 2%.
        - http://news.morningstar.com/classroom2/course.asp?docId=145095&page=9


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
        - Microcap (ensure we can get neccessary data - debt, ROIC, Net operating Assets)
    - long dated option switch - when a later date option becomes a better deal automatically buy it
      and sell the one expiring sooner, valued by BS


Try to copy some of Soros trades from alchemy of finance In my paper account.
    - Equity for stocks, leverage/margin for commodities (futures, bonds, currencies)
    - Hedging currency positions


Generalize ROIC and NOA calculation so we can rank stocks using these measures regardless
if they are micro cap. Would be useful for own portfolio

Implement three O'SAM articles
    - Factors: https://www.osam.com/Commentary/factors-from-scratch
    - Microcaps: https://www.osam.com/Commentary/microcaps-factor-spreads-structural-biases-and-the-institutional-imperative
    - Alpha within Factors: https://www.osam.com/Commentary/alpha-within-factors

'''