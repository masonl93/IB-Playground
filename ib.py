import time
import datetime
from threading import Thread
import pandas
import queue
import sys
import os

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

from ContractSamples import ContractSamples


MA_CROSS = True


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
        print("Position Multi End. Request:", reqId)
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
    def historicalData(self, reqId:int, bar):
        self.hist_data_q.put(bar)
        # print("HistoricalData. ", reqId, " Date:", bar.date, "Open:", bar.open,
        #       "High:", bar.high, "Low:", bar.low, "Close:", bar.close, "Volume:", bar.volume,
        #       "Count:", bar.barCount, "WAP:", bar.average)
    

    @iswrapper
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        super().historicalDataEnd(reqId, start, end)
        print("HistoricalDataEnd ", reqId, "from", start, "to", end)
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
        print("OpenOrderEnd")
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
        print("50 day MA: ", df_ma_50.iloc[-1]['price'])
        print("200 day MA: ", df_ma_200.iloc[-1]['price'])
        if df_ma_50.iloc[-1]['price'] > df_ma_200.iloc[-1]['price']:
            return True
        else:
            return False



if __name__ == '__main__':
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


    if MA_CROSS:
        with open('sp500.txt') as f:
            tickers = [line.rstrip('\n') for line in f]

        contract = Contract()
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"

        for ticker in tickers:
            contract.symbol = ticker
        
            # Only process if no open orders with this ticker
            if not app.orders_df['symbol'].str.contains(ticker).any():
                app.get_historical_data(contract)

                while app.hist_data_df is None:
                    print("Waiting on historical data")
                    time.sleep(1)
                print("Symbol: " + ticker)
                # Golden Cross and not in portfolio -> buy
                if app.movingAvgCross(app.hist_data_df) and not app.positions_df['symbol'].str.contains(ticker).any():
                    print('Placing Buy Order for: ' + ticker)
                    order = Order()
                    order.action = "BUY"
                    order.orderType = "MKT"
                    order.totalQuantity = 1
                    app.place_order(contract, order)
                # Death cross and in portfolio -> sell
                elif app.positions_df['symbol'].str.contains(ticker).any() and not app.movingAvgCross(app.hist_data_df):
                    print('Placing Sell Order for: ' + ticker)
                    order = Order()
                    order.action = "SELL"
                    order.orderType = "MKT"
                    order.totalQuantity = 1
                    app.place_order(contract, order)
                app.hist_data_df = None

    
    


# TODO
'''
- Create screener to find stocks to run Golden cross MA on
(mostly stick to stocks since dont have futures data)

- setup while loop limits (e.g. 10 iterations)

- analysis on fundamental data?

- ML not on stock data but rather on the market participants (e.g. volume, ask/bid spread)

- test open order client id change to 1 or 2 

- fix check if in portfolio (need to make sure its stock)
    - BBT got sold because it has death cross and I own options (should check for STK)
    - BK got sold because I had 'IBKR' in portfolio
    - cannot use contains!
'''