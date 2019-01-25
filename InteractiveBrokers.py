import datetime
import queue
from threading import Thread
import sys
import time
import xml.etree.ElementTree as ET

import pandas
import xmltodict

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

import coaCodes
from ContractSamples import ContractSamples



class App:
    def __init__(self, ip_addr='127.0.0.1', port=7497, clientId=1):

        # Wrapper Methods
        def nextValidId(reqId):
            q.put(reqId)

        def connectionClosed():
            print('CONNECTION HAS CLOSED')

        def error(reqId, errorCode: int, errorString: str):
            if errorCode != 2104 and errorCode != 2106:
                print("Error. Id: ", reqId, " Code: ", errorCode, " Msg: ", errorString)
                if errorCode == 10167 and 'Displaying delayed market data' in errorString:
                    pass
                elif reqId != -1:
                    self.data_errors_q.put((errorString, reqId))
                if 'pacing violation' in errorString:
                    self.slowdown = True
        # Wrapper Methods End

        self.wrapper = EWrapper()
        self.client = EClient(self.wrapper)

        self.client.connect(ip_addr, port, clientId)
        self.ip_addr = ip_addr
        self.my_port = port
        self.my_clientId = clientId
        self.resetData()

        # Wrap wrapper methods
        self.wrap(error)
        self.wrap(connectionClosed)
        self.wrap(nextValidId)

        q = queue.Queue()
        self._thread = Thread(target=self.client.run)
        self._thread.start()
        # Once we get a reqID, we know we can start
        self._reqId = q.get()


    def wrap(self, method):
        def f(wrapper, *args):
            return method(*args)
        name = method.__name__.split('.')[-1]
        setattr(self.wrapper.__class__, name, f)


    def getReqId(self):
        reqId = self._reqId
        self._reqId += 1
        return reqId


    def resetData(self):
        # Historical Data
        self.hist_data_q = queue.Queue()
        self.hist_data_dict_q = {}

        # Fundamental Data
        self.fundamental_data_q = queue.Queue()
        self.slowdown = False

        # Price Data
        self.price_queue = queue.Queue()
        self.close_price_queue = queue.Queue()

        # Dict to map reqId w/ Symbols
        self.reqId_map = {}

        # Errors
        self.data_errors_q = queue.Queue()


    ### Client Functions (with wrapper methods as nested functions) ###

    def getAccounts(self):

        def managedAccounts(accountsList):
            q.put(accountsList)

        q = queue.Queue()
        self.wrap(managedAccounts)
        self.client.reqManagedAccts()
        return q.get()


    def getPositions(self, account):

        def positionMulti(reqId: int, account: str, modelCode: str,
                          contract: Contract, pos: float, avgCost: float):
            positions.append((contract, pos, avgCost))

        def positionMultiEnd(reqId: int):
            q.put(None)

        positions = []
        q = queue.Queue()
        self.wrap(positionMulti)
        self.wrap(positionMultiEnd)
        self.client.reqPositionsMulti(self.getReqId(), account, "")
        q.get()
        return self.getDFPositions(positions)


    def getOrders(self):

        def openOrder(orderId, contract, order, orderState):
            orders.append((contract, order, orderState))

        def openOrderEnd():
            q.put(None)

        orders = []
        q = queue.Queue()
        self.wrap(openOrder)
        self.wrap(openOrderEnd)
        self.client.reqOpenOrders()
        q.get()
        return self.getDFOrders(orders)


    def sellPosition(self, ticker, secType, orders, positions):
        pos = self.getPosDetails(ticker, secType, positions)
        if pos.shape[0] > 1:
            print('Multiple matching positions, defaulting to first record')
            pos = pos.head(0)
        contract = self.createContract(ticker, secType, "USD", "SMART")
        if int(pos['pos']) > 0:
            order = Order()
            order.action = "SELL"
            order.orderType = "MKT"
            order.totalQuantity = int(pos['pos'])
            if not self.duplicateOrder(ticker, secType, order, orders):
                print('Placing SELL order for: ' + ticker)
                self.place_order(contract, order)


    def getHistoricalData(self, contract, duration):
        '''
        Requests historical daily prices

          Input:
            duration: Duration string e.g. "1 Y", "6 M", "3 D", etc
        '''
        def historicalData(reqId:int, bar):
            self.hist_data_dict_q[reqId].put(bar)

        def historicalDataEnd(reqId: int, start: str, end: str):
            dates = []
            prices = []
            while not self.hist_data_dict_q[reqId].empty():
                bar = self.hist_data_dict_q[reqId].get()
                dates.append(bar.date)
                prices.append(bar.close)
            data = {'date': dates, 'price': prices}
            df = pandas.DataFrame(data=data)
            self.hist_data_q.put((df, reqId))

        self.wrap(historicalData)
        self.wrap(historicalDataEnd)
        queryTime = datetime.datetime.today().strftime("%Y%m%d %H:%M:%S")
        reqId = self.getReqId()
        self.client.reqHistoricalData(reqId, contract, queryTime,
                               duration, "1 day", "MIDPOINT", 1, 1, False, [])
        self.reqId_map[reqId] = contract.symbol
        self.hist_data_dict_q[reqId] = queue.Queue()


    def getPrice(self, contract):
        '''
        Requests last trade price
        '''
        def tickPrice(reqId, tickType, price: float,
                    attrib):
            if price == -1:
                # print("No Price Data currently available")
                pass
            # Last price
            elif tickType == 4:
                self.price_queue.put((price, reqId))
            # Previous Close Price
            elif tickType == 9:
                self.close_price_queue.put((price, reqId))
            # Delayed Last Price
            elif tickType == 68:
                self.price_queue.put((price, reqId))
            # Delayed Close Price
            elif tickType == 75:
                self.close_price_queue.put((price, reqId))

        self.wrap(tickPrice)
        if contract.currency != 'USD':
            self.client.reqMarketDataType(3)
        reqId = self.getReqId()
        self.client.reqMktData(reqId, contract, "", True, False, [])
        self.reqId_map[reqId] = contract.symbol
        if contract.currency != 'USD':
            # Go back to live/frozen
            self.client.reqMarketDataType(2)


    def findContracts(self, sybmol):
        self.client.reqMatchingSymbols(self.getReqId(), sybmol)


    def place_order(self, contract, order):
        self.client.placeOrder(self.getReqId(), contract, order)


    def getContractDetails(self, symbol, secType, currency=None, exchange=None):

        def contractDetails(reqId: int, contractDetails):
            contract_details.append(contractDetails)

        def contractDetailsEnd(reqId: int):
            q.put(None)

        contract_details = []
        q = queue.Queue()
        self.wrap(contractDetails)
        self.wrap(contractDetailsEnd)
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        if currency is not None:
            contract.currency = currency
        if exchange is not None:
            contract.exchange = exchange
        self.client.reqContractDetails(self.getReqId(), contract)
        q.get()
        return contract_details


    def getYield(self, contract, data_type=3):

        def tickString(reqId, tickType, value: str):
            for val in value.split(';'):
                if 'YIELD' in val:
                    div.append(float(val.split('=')[1])/100)
            # If ';' in the response, then we know we got the data
            if ';' in value:
                self.client.cancelMktData(reqId)
                q.put(None)

        div = []
        q = queue.Queue()
        self.wrap(tickString)
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        # MarketDataTypeEnum.DELAYED
        if contract.currency != 'USD':
            self.client.reqMarketDataType(data_type)
        self.client.reqMktData(self.getReqId(), contract, "258", False, False, [])
        if contract.currency != 'USD':
            # Go back to live/frozen
            self.client.reqMarketDataType(2)
        q.get()
        if div:
            return div[0]
        else:
            return 0


    def getFinStatements(self, contract, data_type):

        def fundamentalData(reqId, data: str):
            self.fundamental_data_q.put((data, reqId))
            self.client.cancelFundamentalData(reqId)

        self.wrap(fundamentalData)
        reqId = self.getReqId()
        self.client.reqFundamentalData(reqId, contract, data_type, [])
        self.reqId_map[reqId] = contract.symbol


    ### Client Functions End ###


    ### HELPER FUNCTIONS ###

    def getDFPositions(self, positions):
        symbols = []
        types = []
        currencies = []
        sizes = []
        avg_costs = []
        for pos in positions:
            contract, size, cost = pos
            symbols.append(contract.symbol)
            types.append(contract.secType)
            currencies.append(contract.currency)
            sizes.append(size)
            avg_costs.append(cost)
        data = {'symbol': symbols, 'secType': types, 'currency': currencies,
                'pos': sizes, 'avg_cost': avg_costs}
        return pandas.DataFrame(data=data)


    def getDFOrders(self, orders):
        symbols = []
        types = []
        actions = []
        quantities = []
        status = []
        for o in orders:
            contract, order, orderState = o
            symbols.append(contract.symbol)
            types.append(contract.secType)
            actions.append(order.action)
            quantities.append(order.totalQuantity)
            status.append(orderState.status)
        data = {'symbol': symbols, 'secType': types, 'action': actions,
                'quantity': quantities, 'status': status}
        return pandas.DataFrame(data=data)


    def createContract(self, symbol, secType, currency, exchange, primaryExchange=None,
                       right=None, strike=None, expiry=None):
        contract = Contract()
        if type(symbol) is list:
            # Foreign stocks
            print(symbol[0], symbol[1])
            contract.symbol = symbol[0]
            contract.currency = symbol[1]
        else:
            contract.symbol = symbol
            contract.currency = currency
            if primaryExchange:
                contract.primaryExchange = primaryExchange
        contract.secType = secType
        contract.exchange = exchange
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


    def portfolioCheck(self, ticker, positions):
        '''
        Output: Boolean
            True if ticker is in portfolio, is a stock, and position is > 0
            False otherwise
        '''
        matching_ticker_df = positions[positions['symbol'].str.match("^%s$" % ticker)]
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


    def getPosDetails(self, ticker, secType, positions):
        '''
        Returns a dataframe of position details given a ticker and security type
        '''
        matching_ticker_df = positions[positions['symbol'].str.match("^%s$" % ticker)]
        return matching_ticker_df[matching_ticker_df['secType'].str.match("^" + secType + "$")]


    def duplicateOrder(self, ticker, secType, order, orders):
        if not orders.empty:
            return ((orders['symbol'] == ticker) & (orders['secType'] == secType) & (orders['action'] == order.action) & (orders['quantity'] == order.totalQuantity) & (orders['status'] == 'PreSubmitted')).any()
        else:
            return False


    def parseFinancials(self, data, quarterly=False):
        accepted_reports = ["10-K", "10-Q", "Interim Report", "ARS"]

        fundamental_data = xmltodict.parse(data)
        if fundamental_data['ReportFinancialStatements']['FinancialStatements'] is None:
            print('No Fundamental Data')
            if quarterly:
                return None, None, None, None
            return None, None
        try:
            coaMap = fundamental_data['ReportFinancialStatements']['FinancialStatements']['COAMap']
            annuals = fundamental_data['ReportFinancialStatements']['FinancialStatements']['AnnualPeriods']['FiscalPeriod']
            interims = fundamental_data['ReportFinancialStatements']['FinancialStatements']['InterimPeriods']['FiscalPeriod']
        except:
            print('ERROR with fundamental data')
            print(fundamental_data)
            return None, None, None, None

        if quarterly:
            qtr1 = None
            qtr2 = None
            qtr3 = None
            qtr4 = None
            for s in interims:  # loops through each quarterly report
                parsed = {}
                if type(s['Statement']) == list and s['Statement'][0]['FPHeader']['Source']['#text'] in accepted_reports:
                    data = s['Statement']
                    for item in data:  # loops through income statement, balance sheet, and income statement
                        # print(item['@Type'])   ---- this is either INC, BAL, or CAS
                        for i in item['lineItem']:
                            try:
                                parsed[coaCodes.coaCode_map[i['@coaCode']]] = float(i['#text'])
                            except KeyError:
                                print('Could not find coaCode!!!')
                                print(i['@coaCode'])
                                print(coaMap)
                    if qtr1 is None:
                        qtr1 = parsed
                    elif qtr2 is None:
                        qtr2 = parsed
                    elif qtr3 is None:
                        qtr3 = parsed
                    elif qtr4 is None:
                        qtr4 = parsed
            return qtr1, qtr2, qtr3, qtr4
        else:
            current_annual = None
            prev_annual = None
            # only one annual report
            if type(annuals) != list:
                if annuals['Statement'][0]['FPHeader']['Source']['#text'] in accepted_reports:
                    annuals = [annuals]  # making it a list to work in the for loop below
                else:
                    # No annual reports that are of accepted type
                    return current_annual, prev_annual
            for s in annuals:  # loops through each annual report
                parsed = {}
                if type(s['Statement']) == list and s['Statement'][0]['FPHeader']['Source']['#text'] in accepted_reports:
                    data = s['Statement']
                    for item in data:  # loops through income statement, balance sheet, and income statement
                        # print(item['@Type'])   ---- this is either INC, BAL, or CAS
                        for i in item['lineItem']:
                            try:
                                parsed[coaCodes.coaCode_map[i['@coaCode']]] = float(i['#text'])
                            except KeyError:
                                print('Could not find coaCode!!!')
                                print(i['@coaCode'])
                                print(coaMap)
                    if current_annual is None:
                        current_annual = parsed
                    elif prev_annual is None:
                        prev_annual = parsed
            return current_annual, prev_annual