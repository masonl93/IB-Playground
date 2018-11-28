import datetime
import queue
from threading import Thread
import time

import pandas

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

from ContractSamples import ContractSamples


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

        # Fundamental
        self.fundamental_data = None
        self.debt2equity = None
        self.contract_price = None
        self.contract_yield = 0

        # Contract Details
        self.contract_details = []
        self.contract_details_flag = False

        thread = Thread(target=self.run)
        thread.start()


    ### Wrapper Functions ###

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
        self.contract_details.append(contractDetails)
        # print(contractDetails)

    @iswrapper
    def contractDetailsEnd(self, reqId: int):
        super().contractDetailsEnd(reqId)
        # print("ContractDetailsEnd. ", reqId, "\n")
        self.contract_details_flag = True


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

    @iswrapper
    def fundamentalData(self, reqId, data: str):
        super().fundamentalData(reqId, data)
        # print("FundamentalData. ", reqId, data)
        self.fundamental_data = data


    ### mkt data wrappers
    @iswrapper
    def tickGeneric(self, reqId, tickType, value: float):
        super().tickGeneric(reqId, tickType, value)
        # print("Tick Generic. Ticker Id:", reqId, "tickType:", tickType, "Value:", value)
        # print('Tick: Generic')


    @iswrapper
    def tickPrice(self, reqId, tickType, price: float,
                  attrib):
        super().tickPrice(reqId, tickType, price, attrib)
        # print("Tick Price. Ticker Id:", reqId, "tickType:", tickType,
        #       "Price:", price, "CanAutoExecute:", attrib.canAutoExecute,
        #       "PastLimit:", attrib.pastLimit, end=' ')
        # print('Tick: Price')


    @iswrapper
    def tickSize(self, reqId, tickType, size: int):
        super().tickSize(reqId, tickType, size)
        # print("Tick Size. Ticker Id:", reqId, "tickType:", tickType, "Size:", size)
        # print("Tick: Size")


    @iswrapper
    def tickString(self, reqId, tickType, value: str):
        super().tickString(reqId, tickType, value)
        # print("Tick string. Ticker Id:", reqId, "Type:", tickType, "Value:", value)
        # print('Tick: String')
        for val in value.split(';'):
            if 'QTOTD2EQ' in val:
                self.debt2equity = val.split('=')[1]
            if 'NPRICE' in val:
                self.contract_price = val.split('=')[1]
            if 'YIELD' in val:
                self.contract_yield = float(val.split('=')[1])/100
        if ';' in value:
            self.cancelMktData(reqId)

    @iswrapper
    def symbolSamples(self, reqId: int,
                      contractDescriptions):
        super().symbolSamples(reqId, contractDescriptions)
        print("Symbol Samples. Request Id: ", reqId)

        for contractDescription in contractDescriptions:
            derivSecTypes = ""
            for derivSecType in contractDescription.derivativeSecTypes:
                derivSecTypes += derivSecType
                derivSecTypes += " "
            print("Contract: conId:%s, symbol:%s, secType:%s primExchange:%s, "
                  "currency:%s, derivativeSecTypes:%s" % (
                contractDescription.contract.conId,
                contractDescription.contract.symbol,
                contractDescription.contract.secType,
                contractDescription.contract.primaryExchange,
                contractDescription.contract.currency, derivSecTypes))



    ### Wrapper Functions End ###


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
        self.reqHistoricalData(self.nextValidOrderId, contract, queryTime,
                               "1 Y", "1 day", "MIDPOINT", 1, 1, False, [])
        self.nextValidOrderId += 1


    def findContracts(self, sybmol):
        self.reqMatchingSymbols(self.nextValidOrderId, sybmol)
        self.nextValidOrderId += 1


    def place_order(self, contract, order):
        self.placeOrder(self.nextValidOrderId, contract, order)
        self.nextValidOrderId += 1


    def get_contract_details(self, symbol, secType, currency=None, exchange=None):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        if currency is not None:
            contract.currency = currency
        if exchange is not None:
            contract.exchange = exchange
        self.reqContractDetails(self.nextValidOrderId, contract)
        self.nextValidOrderId += 1


    def createContract(self, symbol, secType, currency, exchange, primaryExchange=None,
                       right=None, strike=None, expiry=None):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.currency = currency
        contract.exchange = exchange
        if primaryExchange:
            contract.primaryExchange = primaryExchange
        if right:
            contract.right = right
        if strike:
            contract.strike = strike
        if expiry:
            contract.lastTradeDateOrContractMonth = expiry
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


    def portfolioCheck(self, ticker):
        '''
        Output: Boolean
            True if ticker is in portfolio, is a stock, and position is > 0
            False otherwise
        '''
        matching_ticker_df = self.positions_df[self.positions_df['symbol'].str.match("^%s$" % ticker)]
        matching_type_df = matching_ticker_df[matching_ticker_df['secType'].str.match("^STK$")]
        return ((matching_type_df['pos'] > 0).any())


    def calcOrderSize(self, price, size):
        '''
        Determines how large the order should be

        Input:
            price: Current share price (float)
            size: How large we want our order to be, in dollar terms (int)

        Output:
            int: number of shares to buy
            Will default to 1 if price > size
        '''
        if price > size:
            return 1
        else:
            return int(size/price)


    def getPosDetails(self, ticker, secType):
        '''
        Returns a dataframe of position details given a ticker and security type
        '''
        matching_ticker_df = self.positions_df[self.positions_df['symbol'].str.match("^%s$" % ticker)]
        return matching_ticker_df[matching_ticker_df['secType'].str.match("^STK$")]


    def getMktData(self, contract):
        # Ratios
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        # MarketDataTypeEnum.DELAYED
        self.reqMarketDataType(3)
        self.reqMktData(self.nextValidOrderId, contract, "258", False, False, [])
        self.nextValidOrderId += 1


    def getFinancialData(self, contract, data_type):
        self.reqFundamentalData(self.nextValidOrderId, contract, data_type, [])
        self.nextValidOrderId += 1


    def duplicateOrder(self, ticker, secType, order):
        return ((self.orders_df['symbol'] == ticker) & (self.orders_df['secType'] == secType) & (self.orders_df['action'] == order.action) & (self.orders_df['quantity'] == order.totalQuantity) & (self.orders_df['status'] == 'PreSubmitted')).any()


    def sellPosition(self, ticker, secType):
        pos = self.getPosDetails(ticker, secType)
        if pos.shape[0] > 1:
            print('Multiple matching positions, defaulting to first record')
            pos = pos.head(0)
        contract = self.createContract(ticker, secType, "USD", "SMART")
        if int(pos['pos']) > 0:
            order = Order()
            order.action = "SELL"
            order.orderType = "MKT"
            order.totalQuantity = int(pos['pos'])
            if not self.duplicateOrder(ticker, secType, order):
                print('Placing SELL order for: ' + ticker)
                self.place_order(contract, order)


    def sellAllPositions(self, save_f=None):
        save_tickers = {}
        throttle_count = 0
        if save_f:
            with open(save_f, 'r') as f:
                save_tickers_list = [line.rstrip('\n') for line in f]
            for ticker in save_tickers_list:
                symbol, secType = ticker.split(',')
                save_tickers[symbol] = secType
            for _ind, row in self.positions_df.iterrows():
                if not (row['symbol'] in save_tickers.keys() and save_tickers[row['symbol']] == row['secType']):
                    self.sellPosition(row['symbol'], row['secType'])
                    throttle_count += 1
                    if throttle_count % 50 == 0:
                        time.sleep(1)
        else:
            for _ind, row in self.positions_df.iterrows():
                self.sellPosition(row['symbol'], row['secType'])
                throttle_count += 1
                if throttle_count % 50 == 0:
                    time.sleep(1)
