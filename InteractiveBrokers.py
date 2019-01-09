import datetime
import queue
from threading import Thread
import sys
import time
import xml.etree.ElementTree as ET

import pandas

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

from ContractSamples import ContractSamples


class TestWrapper(EWrapper):
    def __init__(self):
        EWrapper.__init__(self)


class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class TestApp(TestWrapper, TestClient):
    def __init__(self, ip_addr, port, clientId):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)

        self.connect(ip_addr, port, clientId)
        self.ip_addr = ip_addr
        self.my_port = port
        self.my_clientId = clientId

        self.started = False
        self.nextValidOrderId = None
        self.disconnected = False

        # Portfolio
        self.positions_q = queue.Queue()
        self.positions_df = None

        # Orders
        self.orders_q = queue.Queue()
        self.orders_df = None

        # Errors
        self.thread_errors_q = queue.Queue()
        self.data_errors_q = queue.Queue()

        self.resetData()

        thread = Thread(target=self.threadRun)
        thread.start()


    def threadRun(self):
        try:
            self.run()
        except:
            self.thread_errors_q.put(sys.exc_info())


    def resetData(self):
        # Historical Data
        self.hist_data_q = queue.Queue()
        self.hist_data_df = None

        # Fundamental
        self.fundamental_data = None
        self.fundamental_data_q = queue.Queue()
        self.debt2equity = None
        self.contract_price = None
        self.price_queue = queue.Queue()
        self.close_price_queue = queue.Queue()
        self.reqId_map = {}
        self.contract_yield = 0

        # Contract Details
        self.contract_details = []
        self.contract_details_flag = None

        self.slowdown = False


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
        print("NextValidID: " + str(orderId))
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
        self.cancelPositionsMulti(reqId)
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
        if errorCode != 2104 and errorCode != 2106:
            print("Error. Id: ", reqId, " Code: ", errorCode, " Msg: ", errorString)
            if reqId != -1:
                self.data_errors_q.put((errorString, reqId))
            if 'pacing violation' in errorString:
                self.slowdown = True


    @iswrapper
    def connectionClosed(self):
        print('CONNECTION HAS CLOSED')
        self.disconnected = True



    @iswrapper
    def fundamentalData(self, reqId, data: str):
        super().fundamentalData(reqId, data)
        # print("FundamentalData. ", reqId, data)
        self.fundamental_data = data
        self.fundamental_data_q.put((data, reqId))
        self.cancelFundamentalData(reqId)


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
        if price == -1:
            # print("No Price Data currently available")
            pass
        elif tickType == 4:
            self.price_queue.put((price, reqId))
            # delete this later
            if self.contract_price is None:
                self.contract_price = price
        elif tickType == 9:
            self.close_price_queue.put((price, reqId))


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
            # if 'NPRICE' in val:
            #     self.contract_price = float(val.split('=')[1])
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
        self.nextValidOrderId += 1

        ### Requesting this API client's orders (determined by clientId) ###
        self.reqOpenOrders()

        print("Executing requests ... finished")


    def reconnect(self):
        print("Attempting to reconnect")
        self.disconnect()
        self.started = False
        self.connect(self.ip_addr, self.my_port, self.my_clientId)
        #if self.isConnected()
        if self.twsConnectionTime():
            self.disconnected = False
            return True
        else:
            return False


    def getHistoricalData(self, contract, duration):
        '''
        Requests historical daily prices

          Input:
            duration: Duration string e.g. "1 Y", "6 M", "3 D", etc
        '''
        queryTime = datetime.datetime.today().strftime("%Y%m%d %H:%M:%S")
        self.reqHistoricalData(self.nextValidOrderId, contract, queryTime,
                               duration, "1 day", "MIDPOINT", 1, 1, False, [])
        self.nextValidOrderId += 1


    def getPrice(self, contract):
        '''
        Requests last trade price
        '''
        if contract.currency != 'USD':
            self.reqMarketDataType(3)
        self.reqMktData(self.nextValidOrderId, contract, "", True, False, [])
        self.reqId_map[self.nextValidOrderId] = contract.symbol
        self.nextValidOrderId += 1
        if contract.currency != 'USD':
            # Go back to live/frozen
            self.reqMarketDataType(2)


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


    def getMktData(self, contract, tick, data_type=3):
        # Ratios
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        # MarketDataTypeEnum.DELAYED
        if contract.currency != 'USD':
            self.reqMarketDataType(data_type)
        self.reqMktData(self.nextValidOrderId, contract, tick, False, False, [])
        self.nextValidOrderId += 1
        if contract.currency != 'USD':
            # Go back to live/frozen
            self.reqMarketDataType(2)


    def getFinancialData(self, contract, data_type):
        self.reqFundamentalData(self.nextValidOrderId, contract, data_type, [])
        self.reqId_map[self.nextValidOrderId] = contract.symbol
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


    def parseFinancials(self, data, quarterly=False):
        '''
        Parses Financial Data

        See sample_financialStatement.xml for coaCodes and their corresponding values
        Input:
            data as xml string returned from IB's reqFundamentalData
            quarterly: if True, then will return last four qtrs of data,
                       else returns latest and previous annual reports
        '''

        # Only initialize non-mandatory values to 0
        # All mandatory keys will be checked to see if they exist before calculating
        latest_val = {'acct_payable': 0, 'accrued_expense': 0, 'others': 0, 'payable': 0, 'deferred':0}
        prev_val = {}

        tree = ET.fromstring(data)
        financial_statements = tree.find('FinancialStatements')
        if len(financial_statements) == 0:
            print('Financial Statements missing or not in correct format')
            if quarterly:
                return None, None, None, None
            return None, None

        # financial_statements = [coaMap, annuals, interims]
        # We want to use a 10-K or 10-Q, no 8-K or PRESS reports
        latest = None
        prev = None
        if quarterly:
            two_qtr_ago = None
            three_qtr_ago = None
            reports = financial_statements[2]
            for r in reports:
                if r.find(".//Source").text.startswith(("10-K", "10-Q", "Interim Report")):
                    if latest is None:
                        latest = r
                    elif prev is None:
                        prev = r
                    elif two_qtr_ago is None:
                        two_qtr_ago = r
                    elif three_qtr_ago is None:
                        three_qtr_ago = r
        else:
            reports = financial_statements[1]
            for r in reports:
                if r.find(".//Source").text.startswith(("10-K", "10-Q", "ARS")):
                    if latest is None:
                        latest = r
                    elif prev is None:
                        prev = r
            if latest is None or prev is None:
                print('Annual Financial Statements missing')

        if latest:
            # Pulling values from latest annual report
            if latest.find('.//lineItem[@coaCode="ATOT"]') != None:
                latest_val['total_assets'] = float(latest.find('.//lineItem[@coaCode="ATOT"]').text)
            if latest.find('.//lineItem[@coaCode="ACAE"]') != None:
                # Cash and equivalents
                latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="ACAE"]').text)
            elif latest.find('.//lineItem[@coaCode="ACSH"]') != None:
                # Just cash
                latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="ACSH"]').text)
            elif latest.find('.//lineItem[@coaCode="ACDB"]') != None:
                # Cash & Due from Bank
                latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="ACDB"]').text)
            if latest.find('.//lineItem[@coaCode="LTLL"]') != None:
                latest_val['total_liabilities'] = float(latest.find('.//lineItem[@coaCode="LTLL"]').text)
            if latest.find('.//lineItem[@coaCode="STLD"]') != None:
                latest_val['total_debt'] = float(latest.find('.//lineItem[@coaCode="STLD"]').text)
            if latest.find('.//lineItem[@coaCode="SOPI"]') != None:
                latest_val['operating_profit'] = float(latest.find('.//lineItem[@coaCode="SOPI"]').text)
            if latest.find('.//lineItem[@coaCode="EIBT"]') != None:
                latest_val['income_b4_taxes'] = float(latest.find('.//lineItem[@coaCode="EIBT"]').text)
            if latest.find('.//lineItem[@coaCode="TTAX"]') != None:
                latest_val['taxes'] = float(latest.find('.//lineItem[@coaCode="TTAX"]').text)
            if latest.find('.//lineItem[@coaCode="RTLR"]') != None:
                latest_val['revenue'] = float(latest.find('.//lineItem[@coaCode="RTLR"]').text)
            if latest.find('.//lineItem[@coaCode="LAPB"]') != None:
                latest_val['acct_payable'] = float(latest.find('.//lineItem[@coaCode="LAPB"]').text)
            if latest.find('.//lineItem[@coaCode="LAEX"]') != None:
                latest_val['accrued_expense'] = float(latest.find('.//lineItem[@coaCode="LAEX"]').text)
            if latest.find('.//lineItem[@coaCode="LPBA"]') != None:
                latest_val['payable'] = float(latest.find('.//lineItem[@coaCode="LPBA"]').text)
            if latest.find('.//lineItem[@coaCode="SBDT"]') != None:
                latest_val['deferred'] = float(latest.find('.//lineItem[@coaCode="SBDT"]').text)
            if latest.find('.//lineItem[@coaCode="SOCL"]') != None:
                latest_val['others'] = float(latest.find('.//lineItem[@coaCode="SOCL"]').text)
            if latest.find('.//lineItem[@coaCode="QTCO"]') != None:
                latest_val['shares'] = float(latest.find('.//lineItem[@coaCode="QTCO"]').text)
            if latest.find('.//lineItem[@coaCode="SDBF"]') != None:
                latest_val['eps'] = float(latest.find('.//lineItem[@coaCode="SDBF"]').text)
            if latest.find('.//lineItem[@coaCode="SCSI"]') != None:
                latest_val['cash_investments'] = float(latest.find('.//lineItem[@coaCode="SCSI"]').text)
            if latest.find('.//lineItem[@coaCode="SOPI"]') != None:
                latest_val['op_income'] = float(latest.find('.//lineItem[@coaCode="SOPI"]').text)
            if latest.find('.//lineItem[@coaCode="SDPR"]') != None:
                # Income statement depreciation and amortization
                latest_val['dep_amor'] = float(latest.find('.//lineItem[@coaCode="SDPR"]').text)
            else:
                latest_val['dep_amor'] = 0
                if latest.find('.//lineItem[@coaCode="SDED"]') != None:
                    # Cash Flow statement depreciation
                    latest_val['dep_amor'] = float(latest.find('.//lineItem[@coaCode="SDED"]').text)
                if latest.find('.//lineItem[@coaCode="SAMT"]') != None:
                    # Cash Flow statement amortization
                    latest_val['dep_amor'] += float(latest.find('.//lineItem[@coaCode="SAMT"]').text)
            if latest.find('.//lineItem[@coaCode="QTLE"]') != None:
                latest_val['total_equity'] = float(latest.find('.//lineItem[@coaCode="QTLE"]').text)
            if latest.find('.//lineItem[@coaCode="SRPR"]') != None:
                latest_val['redeemable_preferred'] = float(latest.find('.//lineItem[@coaCode="SRPR"]').text)
            if latest.find('.//lineItem[@coaCode="SPRS"]') != None:
                latest_val['preferred'] = float(latest.find('.//lineItem[@coaCode="SPRS"]').text)
            if latest.find('.//lineItem[@coaCode="OTLO"]') != None:
                latest_val['op_cash_flow'] = float(latest.find('.//lineItem[@coaCode="OTLO"]').text)
            if latest.find('.//lineItem[@coaCode="SCEX"]') != None:
                latest_val['capex'] = float(latest.find('.//lineItem[@coaCode="SCEX"]').text)
            else:
                latest_val['capex'] = 0
            if latest.find('.//lineItem[@coaCode="DDPS1"]') != None:
                latest_val['dividend'] = float(latest.find('.//lineItem[@coaCode="DDPS1"]').text)
            else:
                latest_val['dividend'] = 0

        if prev:
            # Pulling values from previous report
            if prev.find('.//lineItem[@coaCode="ATOT"]') != None:
                prev_val['total_assets'] = float(prev.find('.//lineItem[@coaCode="ATOT"]').text)
            if prev.find('.//lineItem[@coaCode="ACAE"]') != None:
                # Cash and equivalents
                prev_val['cash'] = float(prev.find('.//lineItem[@coaCode="ACAE"]').text)
            elif prev.find('.//lineItem[@coaCode="ACSH"]') != None:
                # Just cash
                prev_val['cash'] = float(prev.find('.//lineItem[@coaCode="ACSH"]').text)
            if prev.find('.//lineItem[@coaCode="SCSI"]') != None:
                prev_val['cash_investments'] = float(prev.find('.//lineItem[@coaCode="SCSI"]').text)
            if prev.find('.//lineItem[@coaCode="LTLL"]') != None:
                prev_val['total_liabilities'] = float(prev.find('.//lineItem[@coaCode="LTLL"]').text)
            if prev.find('.//lineItem[@coaCode="STLD"]') != None:
                prev_val['total_debt'] = float(prev.find('.//lineItem[@coaCode="STLD"]').text)
            if prev.find('.//lineItem[@coaCode="SDBF"]') != None:
                prev_val['eps'] = float(prev.find('.//lineItem[@coaCode="SDBF"]').text)
            if prev.find('.//lineItem[@coaCode="SOPI"]') != None:
                prev_val['op_income'] = float(prev.find('.//lineItem[@coaCode="SOPI"]').text)
            if prev.find('.//lineItem[@coaCode="SDPR"]') != None:
                prev_val['dep_amor'] = float(prev.find('.//lineItem[@coaCode="SDPR"]').text)
            else:
                prev_val['dep_amor'] = 0
                if prev.find('.//lineItem[@coaCode="SDED"]') != None:
                    prev_val['dep_amor'] = float(prev.find('.//lineItem[@coaCode="SDED"]').text)
                if prev.find('.//lineItem[@coaCode="SAMT"]') != None:
                    prev_val['dep_amor'] += float(prev.find('.//lineItem[@coaCode="SAMT"]').text)
            if prev.find('.//lineItem[@coaCode="RTLR"]') != None:
                prev_val['revenue'] = float(prev.find('.//lineItem[@coaCode="RTLR"]').text)
            if prev.find('.//lineItem[@coaCode="OTLO"]') != None:
                prev_val['op_cash_flow'] = float(prev.find('.//lineItem[@coaCode="OTLO"]').text)
            if prev.find('.//lineItem[@coaCode="SCEX"]') != None:
                prev_val['capex'] = float(prev.find('.//lineItem[@coaCode="SCEX"]').text)
            else:
                prev_val['capex'] = 0
            if prev.find('.//lineItem[@coaCode="DDPS1"]') != None:
                prev_val['dividend'] = float(prev.find('.//lineItem[@coaCode="DDPS1"]').text)
            else:
                prev_val['dividend'] = 0

        if quarterly:
            two_qtr = {}
            three_qtr = {}
            if two_qtr_ago:
                if two_qtr_ago.find('.//lineItem[@coaCode="SDBF"]') != None:
                    two_qtr['eps'] = float(two_qtr_ago.find('.//lineItem[@coaCode="SDBF"]').text)
                if two_qtr_ago.find('.//lineItem[@coaCode="SOPI"]') != None:
                    two_qtr['op_income'] = float(two_qtr_ago.find('.//lineItem[@coaCode="SOPI"]').text)
                if two_qtr_ago.find('.//lineItem[@coaCode="SDPR"]') != None:
                    two_qtr['dep_amor'] = float(two_qtr_ago.find('.//lineItem[@coaCode="SDPR"]').text)
                else:
                    two_qtr['dep_amor'] = 0
                    if two_qtr_ago.find('.//lineItem[@coaCode="SDED"]') != None:
                        two_qtr['dep_amor'] = float(two_qtr_ago.find('.//lineItem[@coaCode="SDED"]').text)
                    if two_qtr_ago.find('.//lineItem[@coaCode="SAMT"]') != None:
                        two_qtr['dep_amor'] += float(two_qtr_ago.find('.//lineItem[@coaCode="SAMT"]').text)
                if two_qtr_ago.find('.//lineItem[@coaCode="RTLR"]') != None:
                    two_qtr['revenue'] = float(two_qtr_ago.find('.//lineItem[@coaCode="RTLR"]').text)
                if two_qtr_ago.find('.//lineItem[@coaCode="OTLO"]') != None:
                    two_qtr['op_cash_flow'] = float(two_qtr_ago.find('.//lineItem[@coaCode="OTLO"]').text)
                if two_qtr_ago.find('.//lineItem[@coaCode="SCEX"]') != None:
                    two_qtr['capex'] = float(two_qtr_ago.find('.//lineItem[@coaCode="SCEX"]').text)
                else:
                    two_qtr['capex'] = 0
                if two_qtr_ago.find('.//lineItem[@coaCode="DDPS1"]') != None:
                    two_qtr['dividend'] = float(two_qtr_ago.find('.//lineItem[@coaCode="DDPS1"]').text)
                else:
                    two_qtr['dividend'] = 0

            if three_qtr_ago:
                if three_qtr_ago.find('.//lineItem[@coaCode="SDBF"]') != None:
                    three_qtr['eps'] = float(three_qtr_ago.find('.//lineItem[@coaCode="SDBF"]').text)
                if three_qtr_ago.find('.//lineItem[@coaCode="SOPI"]') != None:
                    three_qtr['op_income'] = float(three_qtr_ago.find('.//lineItem[@coaCode="SOPI"]').text)
                if three_qtr_ago.find('.//lineItem[@coaCode="SDPR"]') != None:
                    three_qtr['dep_amor'] = float(three_qtr_ago.find('.//lineItem[@coaCode="SDPR"]').text)
                else:
                    three_qtr['dep_amor'] = 0
                    if three_qtr_ago.find('.//lineItem[@coaCode="SDED"]') != None:
                        three_qtr['dep_amor'] = float(three_qtr_ago.find('.//lineItem[@coaCode="SDED"]').text)
                    if three_qtr_ago.find('.//lineItem[@coaCode="SAMT"]') != None:
                        three_qtr['dep_amor'] += float(three_qtr_ago.find('.//lineItem[@coaCode="SAMT"]').text)
                if three_qtr_ago.find('.//lineItem[@coaCode="RTLR"]') != None:
                    three_qtr['revenue'] = float(three_qtr_ago.find('.//lineItem[@coaCode="RTLR"]').text)
                if three_qtr_ago.find('.//lineItem[@coaCode="OTLO"]') != None:
                    three_qtr['op_cash_flow'] = float(three_qtr_ago.find('.//lineItem[@coaCode="OTLO"]').text)
                if three_qtr_ago.find('.//lineItem[@coaCode="SCEX"]') != None:
                    three_qtr['capex'] = float(three_qtr_ago.find('.//lineItem[@coaCode="SCEX"]').text)
                else:
                    three_qtr['capex'] = 0
                if three_qtr_ago.find('.//lineItem[@coaCode="DDPS1"]') != None:
                    three_qtr['dividend'] = float(three_qtr_ago.find('.//lineItem[@coaCode="DDPS1"]').text)
                else:
                    three_qtr['dividend'] = 0

            return latest_val, prev_val, two_qtr, three_qtr


        return latest_val, prev_val
