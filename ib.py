import argparse
import datetime
import queue
import time
from threading import Thread
import xml.etree.ElementTree as ET

import pandas

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.account_summary_tags import AccountSummaryTags

from ContractSamples import ContractSamples


LAST_PROCESSED = 'CA'
ISSUE_TICKERS = ['PX', 'CHRW', 'BF.B']


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
        matching_ticker_df = app.positions_df[app.positions_df['symbol'].str.match("^%s$" % ticker)]
        return matching_ticker_df[matching_ticker_df['secType'].str.match("^STK$")]


    def get_fin_data(self, contract, data_type):
        self.reqFundamentalData(self.nextValidOrderId, contract, data_type, [])
        self.nextValidOrderId += 1

        # Ratios
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        # MarketDataTypeEnum.DELAYED
        self.reqMarketDataType(3)
        self.reqMktData(self.nextValidOrderId, contract, "258", False, False, [])
        self.nextValidOrderId += 1


    @iswrapper
    def fundamentalData(self, reqId, data: str):
        super().fundamentalData(reqId, data)
        # print("FundamentalData. ", reqId, data)
        self.fundamental_data = data


    ######## mkt data wrappers
    @iswrapper
    def tickGeneric(self, reqId, tickType, value: float):
        super().tickGeneric(reqId, tickType, value)
        # print("Tick Generic. Ticker Id:", reqId, "tickType:", tickType, "Value:", value)
        print('Tick: Generic')


    @iswrapper
    def tickPrice(self, reqId, tickType, price: float,
                  attrib):
        super().tickPrice(reqId, tickType, price, attrib)
        # print("Tick Price. Ticker Id:", reqId, "tickType:", tickType,
        #       "Price:", price, "CanAutoExecute:", attrib.canAutoExecute,
        #       "PastLimit:", attrib.pastLimit, end=' ')
        print('Tick: Price')


    @iswrapper
    def tickSize(self, reqId, tickType, size: int):
        super().tickSize(reqId, tickType, size)
        # print("Tick Size. Ticker Id:", reqId, "tickType:", tickType, "Size:", size)
        print("Tick: Size")


    @iswrapper
    def tickString(self, reqId, tickType, value: str):
        super().tickString(reqId, tickType, value)
        # print("Tick string. Ticker Id:", reqId, "Type:", tickType, "Value:", value)
        print('Tick: String')
        for ratio in value.split(';'):
            if 'QTOTD2EQ' in ratio:
                self.debt2equity = ratio.split('=')[1]
                self.cancelMktData(reqId)

    ######################


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IB Algo Trader')
    parser.add_argument('-m', '--moving_avg', help='Moving Average Cross', action='store_true')
    parser.add_argument('-o', '--other', help='Other Algo', action='store_true')
    parser.add_argument('-p', '--port', help='Port of TWS (default=7497)', default=7497, type=int)
    args = parser.parse_args()

    app = TestApp("127.0.0.1", args.port, clientId=1)
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
                if app.movingAvgCross(app.hist_data_df) and not app.maPortfolioCheck(ticker):
                    print('Placing Buy Order for: ' + ticker)
                    amt = app.calcOrderSize(float(app.hist_data_df.tail(1)['price']), 1000)
                    order = Order()
                    order.action = "BUY"
                    order.orderType = "MKT"
                    order.totalQuantity = amt
                    app.place_order(contract, order)
                # Death cross and in portfolio -> sell
                elif (app.maPortfolioCheck(ticker) and not app.movingAvgCross(app.hist_data_df)):
                    print('Placing Sell Order for: ' + ticker)
                    pos = app.getPosDetails(ticker, 'STK')
                    if pos.shape[0] > 1:
                        print('Multiple matching positions, defaulting to first record')
                        pos = pos.head(0)
                    order = Order()
                    order.action = "SELL"
                    order.orderType = "MKT"
                    order.totalQuantity = int(pos['pos'])
                    app.place_order(contract, order)
                app.hist_data_df = None
        print("Completed MA Cross Daily Calculations")
    
    if args.other:
        print('Other Algo')

        # save microcap tickers to file, same way as SP500 
        # mkt cap 15m to 200m
        # reasonable vol filter?
        tickers = ['AUTO', "ELMD", "ATXI", "CLBS", "MYO", "CDOR"]
        noas = []
        debts = []
        roics = []
        debt_to_equities = []
        noa_vars = ['total_assets', 'cash', 'total_liabilities', 'total_debt']
        roic_vars = ['operating_profit', 'income_b4_taxes', 'taxes', 'total_assets', 'cash', 'revenue']

        for ticker in tickers:
            # Only initialize non-mandatory values to 0
            # All mandatory keys will be checked to see if they exist before calculating
            latest_val = {'acct_payable': 0, 'accrued_expense': 0, 'others': 0, 'payable': 0, 'deferred':0}
            prev_val = {}

            # Initate requests for data
            contract = app.createContract(ticker, "STK", "USD", "SMART")
            app.get_fin_data(contract, "ReportsFinStatements")

            while app.fundamental_data is None:
                print("Waiting on fundamental data")
                time.sleep(1)

            tree = ET.fromstring(app.fundamental_data)
            financial_statements = tree.find('FinancialStatements')
            # financial_statements = [coaMap, annuals, interims]
            # Using annual reports, could switch to interim results for more recent data
            annuals = financial_statements[1]
            latest = annuals[0]
            prev = annuals[1]

            # Pulling values from latest annual report
            if latest.find('.//lineItem[@coaCode="ATOT"]') != None:
                latest_val['total_assets'] = float(latest.find('.//lineItem[@coaCode="ATOT"]').text)
            if latest.find('.//lineItem[@coaCode="SCSI"]') != None:
                latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="SCSI"]').text)
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

            # Pulling values from previous annual report
            if prev.find('.//lineItem[@coaCode="ATOT"]') != None:
                prev_val['total_assets'] = float(prev.find('.//lineItem[@coaCode="ATOT"]').text)
            if prev.find('.//lineItem[@coaCode="SCSI"]') != None:
                prev_val['cash'] = float(prev.find('.//lineItem[@coaCode="SCSI"]').text)
            if prev.find('.//lineItem[@coaCode="LTLL"]') != None:
                prev_val['total_liabilities'] = float(prev.find('.//lineItem[@coaCode="LTLL"]').text)
            if prev.find('.//lineItem[@coaCode="STLD"]') != None:
                prev_val['total_debt'] = float(prev.find('.//lineItem[@coaCode="STLD"]').text)

            # Perform Calculations - ensure all variables are present

            # Net Operating Assets
            if all(var in latest_val for var in noa_vars) and all(var in prev_val for var in noa_vars):
                noa = (latest_val['total_assets'] - latest_val['cash'] -
                        latest_val['total_liabilities'] - latest_val['total_debt'])
                noa_prev = (prev_val['total_assets'] - prev_val['cash'] -
                             prev_val['total_liabilities'] - prev_val['total_debt'])
                change_noa = (noa - noa_prev)/noa_prev
            else:
                change_noa = "Error"

            # 1 year debt change
            if 'total_debt' in latest_val and 'total_debt' in prev_val:
                change_debt = (latest_val['total_debt'] - prev_val['total_debt'])/prev_val['total_debt']
            else:
                change_debt = "Error"

            # ROIC
            if all(var in latest_val for var in roic_vars):
                tax_rate = latest_val['taxes']/latest_val['income_b4_taxes']
                nopat = latest_val['operating_profit']*(1-tax_rate)
                # TODO: Make this calculation smarter
                excess_cash = latest_val['cash'] - .025*latest_val['revenue']
                nibcl = (latest_val['acct_payable'] + latest_val['accrued_expense'] +
                          latest_val['others'] + latest_val['payable'] + latest_val['deferred'])
                invested_cap = latest_val['total_assets'] - nibcl - excess_cash
                roic = nopat/invested_cap
            else:
                print(latest_val)
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
        print(df)


    print('Shutting down!')
    app.disconnect()

    
    


# TODO
'''
- Current:
    - finish microcap
    - separate code into own classes (IB, MA Cross, ROIC, Micro, etc)
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

- analysis on fundamental data?
    - do a DCF valutation

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
if they are micro cap.

Implement three osam articles - factors from scratch, micro cap, and new one 


Add to README how calculations are done:
# Change in Net Opearating Assets
# NOA = OA - OL
# operating assets = total assets(ATOT) - Cash and Short Term Investments(SCSI)
# operating liabilites = total liabilities(LTLL) - Total debt(STLD)

# ROIC
# ROIC = NOPAT/IC
# NOPAT = Operating Profit(SOPI) * (1-tax_rate)
# Tax_rate = income taxes(TTAX)/net income before taxes(EIBT)
# IC = Total Assets(ATOT) - Non-interest bearing current liabilities - Excess cash
# NIBCL = accounts payable(LAPB) + accrued expenses(LAEX) + other current liabilities(SOCL) +
#         accrued/payable(LPBA) + deferred income(SBDT)
# Excess cash = Cash and Short Term Investments(SCSI) - required_cash
# required_cash = .025*revenue
'''