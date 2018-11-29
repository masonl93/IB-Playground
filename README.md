# IB-Playground
A platform to automate trading through Interactive Brokers using their python API. The project has built in algorithms (see below) that can be used or modified as desired.

- [IB-Playground](#ib-playground)
    - [Setup](#setup)
    - [Usage](#usage)
    - [Algorithms](#algorithms)
        - [Moving Average Cross](#moving-average-cross)
        - [Factor Rankings](#factor-rankings)
        - [Multiples](#multiples)
    - [Notes](#notes)


## Setup
1. Create virtualenv (Optional)
2. Install TWS API client  
`$ cd <dir of TWS API installation>/source/pythonclient`
`$ python setup.py install`
3. Install other requirements  
`$ pip install -r requirements.txt`
4. Follow Interactive Brokers instructions on how to setup TWS and API connections. Ensure the port specified in TWS matches the port used in the code. The port can be specified with the '-p' option.
You can find the port in TWS by File->Global Config->API->Settings  
Highly recommended to use in a paper account!

## Usage
Run the script (displaying input options):  
`$ python main.py -h`  

Simple Moving Average Cross Example:  
`$ python main.py -m`  

Factor Ranking Example:  
`$ python main.py -f -i portfolio.txt`  
This will calculate the various factors for all the tickers in the file (should be capitalized and each ticker on its own line). If '-r' option is provided, then it will rank based on the various factors and remove the bottom decile for each factor. This can be extra handy in screening a large list of stocks such as the entire microcap universe.

Valuing a Warrant using Black Scholes and share dilution:  
`$ python main.py -w -t DSKE -o 35.04`  
This is to value DSKE warrants, and since we provided the number of warrants outstanding (35.04 mil), the valuation will incorporate the dilution.  

Selling all Positions:
1. Create a file 'save_from_sell.txt' with positions that you don't want to delete, formatted with ticker and type per line. For example:  
`AAPL,STK`  
2. Run script with clear option:  
`$ python main.py -c`

## Algorithms
### Moving Average Cross
Using the SP500 stocks, buy shares when the 50-day moving average crosses the 200-day moving average (golden cross) and sell the shares when 200-day moving average crosses the 50-day moving average (death cross)

### Factor Rankings  
Description will be added soon  

### Multiples
Calculate numerous multiples for given stocks that can be used for relative valuation. The following multiples are calculated:  
1. P/E (Price / Earnings)  
   P/E = Share_Price/TTM_EPS  
2. EV/EBITDA (Enterprise_Value/Earnings_Before_Interest_Taxes_Depreciation_Amortization)  
   EV = market cap + debt - cash  
   EBITDA = operating income + depreciation/amortization (Currently being used)  
   Can also be calculated as:  
   EBITDA = net income + depreciation/amortization + interest exp + income taxes  
   EBITDA figures calculated over TTM. We subtract cash from numerator as income from cash is not part of EBITDA. Also need subtract any other assets that are not part of EBITDA such as:  
        - minority holding market value of cross holdings, not book value  
        - majority holding: market cap accounts for partial holding but cash, debt, and EBITDA are all   consolidated on balance sheet at 100% (Currently not being accounted for)


## Notes
- If an error occurs when trying to retreive fundamental data, then restart TWS as this tends to solve the issue.
- reqContractDetails seems to have a limit on one request a minute? This is used in warrant valuation so if you are facing issues on a subsequent run, waiting 60 seconds might resolve the issue