# IB-Playground
A platform to automate trading through Interactive Brokers using their python API.
- [IB-Playground](#ib-playground)
  - [Setup](#setup)
  - [Algorithms](#algorithms)
    - [Moving Average Cross](#moving-average-cross)


## Setup
1. (Optional) Create virtualenv  
2. Install TWS API client  
`$ cd <dir of TWS API installation>/source/pythonclient`  
`$ python setup.py install`  
3. Install other requirements  
`$ pip install -r requirements.txt`  
4. Follow Interactive Brokers instructions on how to setup TWS and API connections. Ensure the port specified in TWS matches the port when instantiating the TestApp() (second argument)  
You can find the port in TWS by File->Global Config->API->Settings  
HIGHLY RECOMMENDED TO USE IN A PAPER ACCOUNT

## Algorithms  
### Moving Average Cross  
Using the SP500 stocks, buy shares when the 50-day moving average crosses the 200-day moving average (golden cross) and sell the shares when 200-day moving average crosses the 50-day moving average (death cross)