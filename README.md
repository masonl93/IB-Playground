# IB-Playground
A platform to automate trading through Interactive Brokers using their python API. The project has built in algorithms (see below) that can be used or modified as desired.

- [IB-Playground](#ib-playground)
  - [Setup](#setup)
  - [Usage](#usage)
  - [Algorithms](#algorithms)
    - [Alpha within Factors](#alpha-within-factors)
    - [Moving Average Cross](#moving-average-cross)
    - [Factor Rankings](#factor-rankings)
    - [Ratios](#ratios)
  - [Notes](#notes)


## Setup
1. Create virtualenv (Optional)
2. Install TWS API client  
`$ cd <dir of TWS API installation>/source/pythonclient`  
In this directory, replace client.py with the client.py in this repo. This updated version has removed a timeout that was causing uneccessary disconnections. After that, install ibapi by running:  
`$ python setup.py install`
3. Return to this git repo and install other requirements  
`$ pip install -r requirements.txt`
4. Follow Interactive Brokers instructions on how to setup TWS and API connections. Ensure the port specified in TWS matches the port used in the code. The port can be specified with the '-p' option.
You can find the port in TWS by File->Global Config->API->Settings  
Highly recommended to use in a paper account!  

## Usage
Run the script (displaying input options):  
`$ python main.py -h`  
'-i' option is used to give each algorithm a list of tickers. This should be a text file with a ticker on each line. An example can be seen at data/sp500.txt  

Simple Moving Average Cross Example:  
`$ python main.py --moving_avg -i data/sp500.txt`  

Factor Ranking Example:  
`$ python main.py --factor -i portfolio.txt`  
This will calculate the various factors for all the tickers in the file (should be capitalized and each ticker on its own line). If '-r' option is provided, then it will rank based on the various factors and remove the bottom decile for each factor. This can be extra handy in screening a large list of stocks such as the entire microcap universe.

Valuing a Warrant using Black Scholes and share dilution:  
`$ python main.py -warrants -t DSKE -o 35.04`  
This is to value DSKE warrants, and since we provided the number of warrants outstanding (35.04 mil), the valuation will incorporate the dilution.  

Ratios:  
`$ python main.py --ratios -i portfolio.txt`  

Selling all Positions:
1. Create a file 'save_from_sell.txt' with positions that you don't want to delete, formatted with ticker and type per line. For example:  
`AAPL,STK`  
2. Run script with clear option:  
`$ python main.py -c`

## Algorithms
### Alpha within Factors
We know the value factor works because the market re-rates a company as it believes it will have declining earnings. This pricing causes the company to trade at a discount to their current earnings. Over the short-term, the market tends to be correct and earnings do slow down. The inefficiency is that the market tends to underestimate the likelihood and extent of the company's eventual recovery. Once the earnings exceed expectations, the market once again re-rates the company and provides excess returns to the shareholders who bought at the beginning of the process. This works on average, so there are companies that have low expectations and come back to outperform. But there are also many value traps where even the market gets it wrong and their earnings deteriorate even worse than priced. It is here
that we try to find clues of future earnings so we can get rid of value traps and improve on the value factor. This is based off an O'Shaughnessy Asset Management research paper titled "Alpha within Factors" by Jesse Livermore, Chris Meredith, and Patrick O’Shaughnessy
(https://www.osam.com/Commentary/alpha-within-factors).  
In order to accomplish this, there will be three steps:  
1) Create a composite value factor. Instead of just using P/E to find cheap stocks, we will use multiple value factors in order to not over-rely on one factor. The value factor is composed of:  
  - P/E
  - EV/EBITDA
  - EV/FCF 
  - EV/S  
Then form a composite score, where a stock in lowest 1% of P/E, will receive rank of 100. If in highest 1%, will receive rank of 1. If missing a score, then assign score of 50. Repeat this for each factor and then add the scores up and take a simple average for the final Value Score. Lastly, we will take the top quintile stocks based off the value score as our starting point. So if we are using the SP500 as an example, we now have 100 stocks with the highest value score.
2) Next we want to attempt to remove value traps.

### Moving Average Cross
Using the SP500 stocks, buy shares when the 50-day moving average crosses the 200-day moving average (golden cross) and sell the shares when 200-day moving average crosses the 50-day moving average (death cross)

### Factor Rankings  
Ranks a list of stocks based on 4 main factors: Change in Net Operating Assets, One Year Change in Debt, Debt to Equity, and Return on Invested Capital. This section was inspired by and based off of an O'Shaughnessy Asset Management research paper titled "Microcaps — Factor Spreads, Structural Biases, and the Institutional Imperative" by Ehren Stanhope (https://www.osam.com/Commentary/microcaps-factor-spreads-structural-biases-and-the-institutional-imperative). While this was origianlly for screening quality microcap companies, the functionality has been expanded to factor rank any given list of tickers. 

### Ratios
Calculate numerous ratios for given stocks that can be used for relative valuation. While one can find many of these ratios precalculated somewhere online, it is not clear how those values are calculated making it difficult to compare and have confidence in the figures. The main purpose here is to have full control over how the values are calculated so we can, with confidence, compare these values. The following are calculated:  
1. P/E (Price / Earnings)  
     P/E = Share_Price/TTM_EPS  
   Drivers: Payout ratio(dividend), Cost of equity, Expected growth rate  
2. EV/EBITDA (Enterprise_Value/Earnings_Before_Interest_Taxes_Depreciation_Amortization)  
     EV = market cap + debt - cash  
     EBITDA = operating income + depreciation/amortization (Currently being used)  
   Can also be calculated as:  
     EBITDA = net income + depreciation/amortization + interest exp + income taxes  
   EBITDA figures calculated over TTM. We subtract cash from numerator as income from cash is not part of EBITDA. Also need subtract any other assets that are not part of EBITDA such as:  
        - minority holding market value of cross holdings, not book value  
        - majority holding: market cap accounts for partial holding but cash, debt, and EBITDA are all   consolidated on balance sheet at 100% (Currently not being accounted for)  
    Drivers: Tax rate, expected growth rate, cost of capital, reinvestment rate
3. P/BV (Price / Book_Value)  
   BV = (Total_Equity - Redeemable_Preferred_Shares - Nonredeemable_Preferred_Shares) / Shares  
   This has historically been a very useful ratio to determine cheapness of a stock but as of late, the usefulness might be dwindling. There is a growing portion of stocks that have a negative equity or have what seems to be an expensive P/B ratio but are on the cheaper side when looking at all other ratios. This can be accounted for with some general changes that have been occuring: Increase of intangible assets that are not represented on the balance sheet (e.g. brand name, human capital, advertising, etc), long term assets depreciating faster than their useful lives, and buybacks/dividends that cause decreases in equity when they exceed net income. See more here: https://osam.com/Commentary/negative-equity-veiled-value-and-the-erosion-of-price-to-book   
   Drivers: Return on equity  
4. EV/S (Enterprise_Value / Sales)  
   S = TTM_Revenue
   The more common ratio is P/S but this is inconsistent since revenue is to the whole firm and not only the equity owners i.e. market cap. These ratios can be handy if one lacks trust in the assumptions made in the accounting or a company is pre-earnings, hence no P/E.  
   Drivers: Margins


## Notes
- If an error occurs when trying to retreive fundamental data, then restart TWS as this tends to solve the issue.
- reqContractDetails() is throttled when searching contracts and not providing an expiry date. Since this is what we need to use to smartly find all warrants given a stock symbol, one might need to wait 60 seconds in order to run warrant valuation a subsequent time. (TODO: Look into reqSecDefOptParams() as this is not throttled and is used to find option chains, not sure if it will work for warrants)
- Some issues might arise if you do not have the neccessary market data subscriptions. For example, I do not have any foreign market data subscriptions so when my input file has foreign stocks, it is hit or miss on if I can successfully get a price back from the API.