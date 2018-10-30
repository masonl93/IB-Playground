from threading import Thread
import time
import queue

from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.client import EClient
from ibapi.utils import iswrapper
from ibapi.account_summary_tags import AccountSummaryTags
from ibapi.scanner import ScannerSubscription
from ibapi.object_implem import Object 
from ibapi.contract import *






class TestWrapper(EWrapper):
    """
    The wrapper deals with the action coming back from the IB gateway or TWS instance

    We override methods in EWrapper that will get called when this action happens, like currentTime


    """

    ## error handling code
    def init_error(self):
        error_queue=queue.Queue()
        self._my_errors = error_queue

    def get_error(self, timeout=5):
        if self.is_error():
            try:
                return self._my_errors.get(timeout=timeout)
            except queue.Empty:
                return None

        return None

    def is_error(self):
        an_error_if=not self._my_errors.empty()
        return an_error_if

    def error(self, id, errorCode, errorString):
        ## Overriden method
        errormsg = "IB error id %d errorcode %d string %s" % (id, errorCode, errorString)
        self._my_errors.put(errormsg)

    ## Time telling code
    def init_time(self):
        time_queue=queue.Queue()
        self._time_queue = time_queue

        return time_queue

    def currentTime(self, time_from_server):
        ## Overriden method
        self._time_queue.put(time_from_server)

    @iswrapper
    # ! [managedaccounts]
    def managedAccounts(self, accountsList: str):
        super().managedAccounts(accountsList)
        print("Account list: ", accountsList)
        # ! [managedaccounts]

        # self.account = accountsList.split(",")[0]
        print(accountsList.split(",")[0])

    @iswrapper
    # ! [accountsummary]
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,
                       currency: str):
        super().accountSummary(reqId, account, tag, value, currency)
        print("Acct Summary. ReqId:", reqId, "Acct:", account,
              "Tag: ", tag, "Value:", value, "Currency:", currency)



    # @iswrapper
    # # ! [position]
    # def position(self, account: str, contract: Contract, position: float,
    #              avgCost: float):
    #     super().position(account, contract, position, avgCost)
    #     print("Position.", account, "Symbol:", contract.symbol, "SecType:",
    #           contract.secType, "Currency:", contract.currency,
    #           "Position:", position, "Avg cost:", avgCost)

    @iswrapper
    # ! [positionmulti]
    def positionMulti(self, reqId: int, account: str, modelCode: str,
                      contract: Contract, pos: float, avgCost: float):
        super().positionMulti(reqId, account, modelCode, contract, pos, avgCost)
        print("ModelCode:", modelCode, "Symbol:", contract.symbol, "SecType:",
              contract.secType, "Currency:", contract.currency, ",Position:",
              pos, "AvgCost:", avgCost)
        # print("Position Multi. Request:", reqId, "Account:", account,
        #       "ModelCode:", modelCode, "Symbol:", contract.symbol, "SecType:",
        #       contract.secType, "Currency:", contract.currency, ",Position:",
        #       pos, "AvgCost:", avgCost)

    
    @iswrapper
    # ! [scannerdata]
    def scannerData(self, reqId: int, rank: int, contractDetails: ContractDetails,
                    distance: str, benchmark: str, projection: str, legsStr: str):
        super().scannerData(reqId, rank, contractDetails, distance, benchmark,
                            projection, legsStr)
        print("ScannerData. ", reqId, "Rank:", rank, "Symbol:", contractDetails.contract.symbol,
              "SecType:", contractDetails.contract.secType,
              "Currency:", contractDetails.contract.currency,
              "Distance:", distance, "Benchmark:", benchmark,
              "Projection:", projection, "Legs String:", legsStr)

    # ! [scannerdata]

    @iswrapper
    # ! [scannerparameters]
    def scannerParameters(self, xml: str):
        super().scannerParameters(xml)
        open('log/scanner.xml', 'w').write(xml)

    # ! [scannerparameters]


class TestClient(EClient):
    """
    The client method

    We don't override native methods, but instead call them from our own wrappers
    """
    def __init__(self, wrapper):
        ## Set up with a wrapper inside
        EClient.__init__(self, wrapper)

    def speaking_clock(self):
        """
        Basic example to tell the time
        :return: unix time, as an int
        """

        print("Getting the time from the server... ")
        ## Make a place to store the time we're going to return
        ## This is a queue
        time_storage = self.wrapper.init_time()

        ## This is the native method in EClient, asks the server to send us the time please
        self.reqCurrentTime()

        ## Try and get a valid time
        MAX_WAIT_SECONDS = 10

        try:
            current_time = time_storage.get(timeout=MAX_WAIT_SECONDS)
        except queue.Empty:
            print("Exceeded maximum wait for wrapper to respond")
            current_time = None
        while self.wrapper.is_error():
            print("ERROR:    " + self.get_error())
        return current_time


    def get_account_info(self):
        self.reqManagedAccts()
        self.reqAccountSummary(9001, "All", AccountSummaryTags.AllTags)
        self.reqPositionsMulti(9006, "U2338860", "")
        # self.reqPositionsMulti(9006, self.account, "")




class TestApp(TestWrapper, TestClient):
    '''
    Main App Class

    Holds the TestWrapper and TestClient

    Client = Sends requests to the server
    Wrapper = Receives responses from the server
    '''
    def __init__(self, ipaddress, port, clientid):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)

        self.connect(ipaddress, port, clientid)

        thread = Thread(target=self.run)
        thread.start()

        setattr(self, "_thread", thread)

        self.init_error()


if __name__ == '__main__':

    app = TestApp("127.0.0.1", 7497, 0)
    current_time = app.speaking_clock()
    app.get_account_info()
    print(current_time)
    time.sleep(30)
    app.disconnect()