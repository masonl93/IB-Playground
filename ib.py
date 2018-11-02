import argparse
import datetime
import queue
import time
from threading import Thread

import pandas

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

from ContractSamples import ContractSamples


LAST_PROCESSED = None
ISSUE_TICKERS = ['PX']


class TestWrapper(EWrapper):
    pass
   

class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class TestApp(TestWrapper, TestClient):
    def __init__(self, ip_addr, port, clientId):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)

        self.connect(ip_addr, port, clientId)

        self.started = False
        self.nextValidOrderId = None

        # Historical Data
        self.hist_data_q = queue.Queue()
        self.hist_data_df = None

        # Portfolio
        self.positions_q = queue.Queue()
        self.positions_df = None

        # Orders
        self.orders_q = queue.Queue()
        self.orders_df = None

        thread = Thread(target=self.run)
        thread.start()


    @iswrapper
    def managedAccounts(self, accountsList: str):
        super().managedAccounts(accountsList)
        print("Account list: ", accountsList)

        self.account = accountsList.split(",")[0]


    @iswrapper
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)

        self.nextValidOrderId = orderId

        # we can start now
        self.start()


    def start(self):
        if self.started:
            return

        self.started = True

        print("Executing requests")
        ### Time ###
        self.reqCurrentTime()

        ### Account Summary ###
        # self.reqAccountSummary(1, "All", AccountSummaryTags.AllTags)

        ### Positions ###
        self.reqPositionsMulti(self.nextValidOrderId, self.account, "")

        ### Requesting this API client's orders (determined by clientId) ###
        self.reqOpenOrders()

        print("Executing requests ... finished")


    def get_historical_data(self, contract):
        queryTime = datetime.datetime.today().strftime("%Y%m%d %H:%M:%S")
        self.reqHistoricalData(2, contract, queryTime,
                               "1 Y", "1 day", "MIDPOINT", 1, 1, False, [])


    def place_order(self, contract, order):
        self.placeOrder(self.nextValidOrderId, contract, order)
        self.nextValidOrderId += 1


    def get_contract_details(self, symbol, secType=None, currency=None, exchange=None):
        contract = Contract()
        if symbol is not None:
           contract.symbol = symbol
        if secType is not None:
            contract.secType = secType
        if currency is not None:
            contract.currency = currency
        if exchange is not None:
            contract.exchange = exchange
        self.reqContractDetails(1, contract)


    @iswrapper
    def execDetails(self, reqId, contract, execution):
        # print('ExecDetails')
        # print(execution)
        pass


    @iswrapper
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permid,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        # print('Order Status')
        # print(status)
        pass


    @iswrapper
    def positionMulti(self, reqId: int, account: str, modelCode: str,
                      contract: Contract, pos: float, avgCost: float):
        super().positionMulti(reqId, account, modelCode, contract, pos, avgCost)
        # print("Position Multi. Request:", reqId, "Account:", account,
        #       "ModelCode:", modelCode, "Symbol:", contract.symbol, "SecType:",
        #       contract.secType, "Currency:", contract.currency, ",Position:",
        #       pos, "AvgCost:", avgCost)
        self.positions_q.put((contract, pos, avgCost))


    @iswrapper
    def positionMultiEnd(self, reqId: int):
        super().positionMultiEnd(reqId)
        # 
        # print("Position Multi End. Request:", reqId)
        symbols = []
        types = []
        currencies = []
        positions = []
        avg_costs = []
        while not self.positions_q.empty():
            contract, pos, cost = self.positions_q.get()
            symbols.append(contract.symbol)
            types.append(contract.secType)
            currencies.append(contract.currency)
            positions.append(pos)
            avg_costs.append(cost)
        data = {'symbol': symbols, 'secType': types, 'currency': currencies,
                'pos': positions, 'avg_cost': avg_costs}
        self.positions_df = pandas.DataFrame(data=data)


    @iswrapper
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,
                       currency: str):
        super().accountSummary(reqId, account, tag, value, currency)
        print("Acct Summary. ReqId:", reqId, "Acct:", account,
              "Tag: ", tag, "Value:", value, "Currency:", currency)


    @iswrapper
    def contractDetails(self, reqId: int, contractDetails):
        super().contractDetails(reqId, contractDetails)
        print(contractDetails)

    @iswrapper
    def contractDetailsEnd(self, reqId: int):
        super().contractDetailsEnd(reqId)
        print("ContractDetailsEnd. ", reqId, "\n")


    @iswrapper
    def historicalData(self, reqId:int, bar):
        self.hist_data_q.put(bar)
        # print("HistoricalData. ", reqId, " Date:", bar.date, "Open:", bar.open,
        #       "High:", bar.high, "Low:", bar.low, "Close:", bar.close, "Volume:", bar.volume,
        #       "Count:", bar.barCount, "WAP:", bar.average)
    

    @iswrapper
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        super().historicalDataEnd(reqId, start, end)
        # print("HistoricalDataEnd ", reqId, "from", start, "to", end)
        dates = []
        prices = []
        while not self.hist_data_q.empty():
            bar = self.hist_data_q.get()
            dates.append(bar.date)
            prices.append(bar.close)
        data = {'date': dates, 'price': prices}
        self.hist_data_df = pandas.DataFrame(data=data)


    @iswrapper
    def openOrder(self, orderId, contract, order,
                  orderState):
        super().openOrder(orderId, contract, order, orderState)
        self.orders_q.put((contract, order, orderState))


    @iswrapper
    def openOrderEnd(self):
        super().openOrderEnd()
        # print("OpenOrderEnd")
        symbols = []
        types = []
        actions = []
        quantities = []
        status = []
        while not self.orders_q.empty():
            contract, order, orderState = self.orders_q.get()
            symbols.append(contract.symbol)
            types.append(contract.secType)
            actions.append(order.action)
            quantities.append(order.totalQuantity)
            status.append(orderState.status)
        data = {'symbol': symbols, 'secType': types, 'action': actions,
                'quantity': quantities, 'status': status}
        self.orders_df = pandas.DataFrame(data=data)


    @iswrapper
    def currentTime(self, time):
        # super().currentTime(time)
        print("TIME: ", time)


    @iswrapper
    def error(self, reqId, errorCode: int, errorString: str):
        # super().error(reqId, errorCode, errorString)
        if 'farm connection is OK' not in errorString:
            print("Error. Id: ", reqId, " Code: ", errorCode, " Msg: ", errorString)


    def movingAvgCross(self, df):
        '''
        
        Output: Boolean
            True if 50-day Moving Avg is greater than 200-day Moving Avg
            False otherwise
        '''
        df_ma_50 = df.rolling(window=50).mean()
        df_ma_200 = df.rolling(window=200).mean()
        # print("50 day MA: ", df_ma_50.iloc[-1]['price'])
        # print("200 day MA: ", df_ma_200.iloc[-1]['price'])
        if df_ma_50.iloc[-1]['price'] > df_ma_200.iloc[-1]['price']:
            return True
        else:
            return False


    def createContract(self, symbol, secType, currency, exchange, primaryExchange=None):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.currency = currency
        contract.exchange = exchange
        if primaryExchange:
            contract.primaryExchange = primaryExchange
        return contract


    def createOptionContract(self, symbol, currency, exchange):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency
        contract.lastTradeDateOrContractMonth = "201901"
        contract.strike = 150
        contract.right = "C"
        contract.multiplier = "100"
        return contract


    def maPortfolioCheck(self, ticker):
        '''
        Output: Boolean
            True if ticker is in portfolio, is a stock, and position is > 0
            False otherwise
        '''
        matching_ticker_df = app.positions_df[app.positions_df['symbol'].str.match("^%s$" % ticker)]
        matching_type_df = matching_ticker_df[matching_ticker_df['secType'].str.match("^STK$")]
        return ((matching_type_df['pos'] > 0).any())


    def get_fin_data(self, contract, data_type):
        self.reqFundamentalData(self.nextValidOrderId, ContractSamples.USStock(), data_type, [])
        self.nextValidOrderId += 1


    @iswrapper
    # ! [fundamentaldata]
    def fundamentalData(self, reqId, data: str):
        super().fundamentalData(reqId, data)
        print("FundamentalData. ", reqId, data)
    # ! [fundamentaldata]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    parser.add_argument('-m', '--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('-o', '--other', help='Other Algo', action='store_true')
    args = parser.parse_args()

    app = TestApp("127.0.0.1", 7497, clientId=1)
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
            start_index = tickers.index(LAST_PROCESSED)
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
                if app.movingAvgCross(app.hist_data_df) and not app.maPortfolioCheck(ticker):
                    print('Placing Buy Order for: ' + ticker)
                    order = Order()
                    order.action = "BUY"
                    order.orderType = "MKT"
                    order.totalQuantity = 1
                    app.place_order(contract, order)
                # Death cross and in portfolio -> sell
                elif (app.maPortfolioCheck(ticker) and not app.movingAvgCross(app.hist_data_df)):
                    print('Placing Sell Order for: ' + ticker)
                    order = Order()
                    order.action = "SELL"
                    order.orderType = "MKT"
                    order.totalQuantity = 1
                    app.place_order(contract, order)
                app.hist_data_df = None
        print("Completed MA Cross Daily Calculations")
    
    if args.other:
        print('Other Algo')
        contract = app.createContract("AMZN", "STK", "USD", "SMART")

        # app.get_fin_data(contract, "ReportRatios")
        # app.reqFundamentalData(8001, contract, "ReportRatios", [])
        app.get_historical_data(contract)

        while app.hist_data_df is None:
            print("Waiting on historical data")
            time.sleep(1)
        print(app.hist_data_df)

    print('Shutting down!')
    app.disconnect()

    
    


# TODO
'''
- setup while loop limits (e.g. 10 iterations)

- analysis on fundamental data?

- use more threads?

- set stop loss mechanism?

- integrate backtester, make my own - follow logic of open sourced one

- test if hist data for TSE works during market hours.

- separate non IB code (i.e. algo code) into own class/functions in other file

- strategies:
(https://www.investopedia.com/articles/active-trading/101014/basics-algorithmic-trading-concepts-and-examples.asp)
    - Trend Following
        - MA Cross
    - Arbitrage
        - OTC stocks tough since don't have foreign mkt data subscriptions
    - ML
        - not on stock data but rather on the market participants (e.g. volume, ask/bid spread)
        - weighting different factors in a multi-factor model - instead of linear weighting, could use 
          non-linear relationships from ML
    - Taleb strategies? Barbell, etc
    - Put-call parity
    - Microcap strategy
        - ensure we can get neccessary data - debt, ROIC, Net operating Assets

- long dated option switch - when a later date option becomes a better deal automatically buy it
  and sell the one expiring sooner, valued by BS

- increase order size so commisions aren't killing us (do it dollar based, not order size)
'''