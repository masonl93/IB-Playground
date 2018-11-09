# IB-Playground
A platform to automate trading through Interactive Brokers using their python API. The project has built in algorithms (see below) that can be used or modified as desired.  

- [IB-Playground](#ib-playground)
    - [Setup](#setup)
    - [Usage](#usage)
    - [Algorithms](#algorithms)
        - [Moving Average Cross](#moving-average-cross)
        - [Factor Rankings](#factor-rankings)


## Setup
1. Create virtualenv (Optional)  
2. Install TWS API client  
`$ cd <dir of TWS API installation>/source/pythonclient`  
`$ python setup.py install`  
3. Install other requirements  
`$ pip install -r requirements.txt`  
4. Follow Interactive Brokers instructions on how to setup TWS and API connections. Ensure the port specified in TWS matches the port used in the code. The port can be specified with the '-p' option.    
You can find the port in TWS by File->Global Config->API->Settings  
HIGHLY RECOMMENDED TO USE IN A PAPER ACCOUNT

## Usage  
Run the script (displaying input options):  
`$ python main.py -h`  

Simple Moving Average Cross Example:  
`$ python main.py -m`

## Algorithms  
### Moving Average Cross  
Using the SP500 stocks, buy shares when the 50-day moving average crosses the 200-day moving average (golden cross) and sell the shares when 200-day moving average crosses the 50-day moving average (death cross)  

### Factor Rankings