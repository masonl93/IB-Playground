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

        self.hist_data_q = queue.Queue()
        self.positions_q = queue.Queue()
        self.positions_df = None
        self.nextValidOrderId = None
        self.df = None
        self.FINISHED = False
        self.contract_details = None

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
        # self.reqCurrentTime()

        ### Account Summary ###
        # self.reqAccountSummary(1, "All", AccountSummaryTags.AllTags)

        ### Positions ###
        self.reqPositionsMulti(self.nextValidOrderId, self.account, "")

        ### Find matching contract ###
        # self.get_contract_details(symbol="IBKR", secType="STK")
        # self.get_contract_details("AAPL", secType="STK", currency="USD")
        # self.get_contract_details("CL", secType="FUT", currency="USD")

        ### Historical data ###
        self.get_historical_data(ContractSamples.USStock())
        # self.get_historical_data(ContractSamples.SimpleFuture())
        # self.place_order(ContractSamples.SimpleOilFuture())

        ### Streaming data ###
        # self.get_mkt_data()

        ### Placing order ###
        # self.place_order()

        print("Executing requests ... finished")

        # while True:
        #     if self.FINISHED:
        #         print('QUITTING')
        #         os._exit(1)
        #     else:
        #         print('Just loopin around')
        #         time.sleep(5)

    def get_historical_data(self, contract=None):
        # queryTime = (datetime.datetime.today() - datetime.timedelta(days=180)).strftime("%Y%m%d %H:%M:%S")
        queryTime = datetime.datetime.today().strftime("%Y%m%d %H:%M:%S")
        if contract is None:
            contract = Contract()
            contract.symbol = "DOV"
            contract.secType = "STK"
            contract.currency = "USD"
            contract.exchange = "SMART"
        self.contract_details = contract
        self.reqHistoricalData(2, contract, queryTime,
                               "1 Y", "1 day", "MIDPOINT", 1, 1, False, [])

    # def get_mkt_data(self):
    #     contract = Contract()
    #     contract.symbol = "IBKR"
    #     contract.secType = "STK"
    #     contract.currency = "USD"
    #     contract.exchange = "SMART"
    #     self.reqMktData(3, contract, "", False, False, [])


    def place_order(self, contract=None):
        # contract = Contract()
        # contract.symbol = "DOV"
        # contract.secType = "STK"
        # contract.currency = "USD"
        # contract.exchange = "SMART"
        order = Order()
        order.action = "BUY"
        order.orderType = "MKT"
        # order.orderType = "LMT"
        # order.lmtPrice = 55
        order.totalQuantity = 1

        if contract is None:
            self.placeOrder(self.nextValidOrderId, self.contract_details, order)
        else:
            self.placeOrder(self.nextValidOrderId, contract, order)

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
        print('ExecDetails')
        print(execution)


    @iswrapper
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permid,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print('Order Status')
        print(status)


    @iswrapper
    def openOrder(self, orderId, contract, order, orderstate):
        print('Order Open')
        print(orderstate)



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
        print('POSITIONS:')
        print(self.positions_df)


    @iswrapper
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,
                       currency: str):
        super().accountSummary(reqId, account, tag, value, currency)
        print("Acct Summary. ReqId:", reqId, "Acct:", account,
              "Tag: ", tag, "Value:", value, "Currency:", currency)

    @iswrapper
    def contractDetails(self, reqId: int, contractDetails):
        # super().contractDetails(reqId, contractDetails)
        # print(contractDetails)
        if self.contract_details is None:
            self.contract_details = contractDetails.contract
        print(contractDetails.contract)

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
        print("Queue Contents")
        dates = []
        prices = []
        while not self.hist_data_q.empty():
            bar = self.hist_data_q.get()
            dates.append(bar.date)
            prices.append(bar.close)
        data = {'date': dates, 'price': prices}
        self.df = pandas.DataFrame(data=data)
        # print("COMPLETE DF:")
        # for ind, row in self.df.iterrows():
        #     print(ind)
        #     print(row['date'], row['price'])
        # self.FINISHED = True
        df_ma_50 = self.df.rolling(window=50).mean()
        df_ma_200 = self.df.rolling(window=200).mean()
        print("50 day MA: ", df_ma_50.iloc[-1]['price'])
        print("200 day MA: ", df_ma_200.iloc[-1]['price'])
        if df_ma_50.iloc[-1]['price'] > df_ma_200.iloc[-1]['price']:
            self.place_order()

        

    @iswrapper
    def currentTime(self, time):
        super().currentTime(time)
        print("TIME: ", time)

    @iswrapper
    def error(self, reqId, errorCode: int, errorString: str):
        # super().error(reqId, errorCode, errorString)
        if 'farm connection is OK' not in errorString:
            print("Error. Id: ", reqId, " Code: ", errorCode, " Msg: ", errorString)



if __name__ == '__main__':
    app = TestApp("127.0.0.1", 7497, clientId=0)
    # app.connect("127.0.0.1", 7497, clientId=0)
    print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                  app.twsConnectionTime()))
    # app.run()
    time.sleep(5)
    print(app.positions_df)
    print('hello')




# TODO
'''
- Put positions in a nice list so we don't buy samething over and over

- Create screener to find stocks to run Golden cross MA on

- mostly stick to stocks since dont have futures data

- move MA calc outside of histdataend func
'''