# IB-Playground
A platform to automate trading through Interactive Brokers using their python API. The project has built in algorithms (see below) that can be used or modified as desired.

- [IB-Playground](#ib-playground)
  - [Setup](#setup)
  - [Usage](#usage)
  - [Algorithms](#algorithms)
    - [Alpha within Factors](#alpha-within-factors)
    - [Factor Rankings](#factor-rankings)
    - [Ratios](#ratios)
    - [Moving Average Cross](#moving-average-cross)
  - [Performance](#performance)


## Setup
1. Create virtualenv (Optional)
2. Install TWS API client  
`$ cd <dir of TWS API installation>/source/pythonclient`  
Install ibapi by running:  
`$ python setup.py install`
3. Return to this git repo and install other requirements  
`$ pip install -r requirements.txt`
4. Follow Interactive Brokers instructions on how to setup TWS and API connections. Ensure the port specified in TWS matches the port used in the code. The port can be specified with the '-p' option.
You can find the port in TWS by File->Global Config->API->Settings  
Highly recommended to use in a paper account!  

## Usage
Run the script (displaying input options):  
`$ python main.py -h`  

'-i' option is used to give each algorithm a list of tickers. This should be a text file with a ticker on each line. An example can be seen at data/sp500.txt. One can also include foreign stocks by including a '\$' after the ticker and followed by the currency of the stock. For example, Bollore, the French conglomerate that is traded on the Paris exchange in Euros would be: BOL$EUR  

Alpha within Factors:  
`$ python main.py --factor_alpha -i data/sp500.txt`  

Ratios:  
`$ python main.py --ratios -i portfolio.txt`  
or for just one ticker:  
`$ python main.py --ratios -t AAPL` 

Factor Ranking Example:  
`$ python main.py --factor -i portfolio.txt`  
This will calculate the various factors for all the tickers in the file (should be capitalized and each ticker on its own line). If '-r' option is provided, then it will rank based on the various factors and remove the bottom decile for each factor. This can be extra handy in screening a large list of stocks such as the entire microcap universe.

Valuing a Warrant using Black Scholes and share dilution:  
`$ python main.py --warrants -t DSKE -o 35.04`  
This is to value DSKE warrants, and since we provided the number of warrants outstanding (35.04 mil), the valuation will incorporate the dilution.  

Simple Moving Average Cross Example:  
`$ python main.py --moving_avg -i data/sp500.txt`  
Include the '--buy' option to actually execute the trades i.e. buy or sell on crosses.  

Save dataframe results (in pickle format) by using '--output' option and a file name.

Selling all Positions:
1. Create a file 'save_from_sell.txt' with positions that you don't want to delete, formatted with ticker and type per line. For example:  
`AAPL,STK`  
2. Run script with clear option:  
`$ python main.py --clear`  

Run tests (from root dir):  
`$ pytest`


## Algorithms
### Alpha within Factors
We know the value factor works because the market re-rates a company as it believes it will have declining earnings. This pricing causes the company to trade at a discount to their current earnings. Over the short-term, the market tends to be correct and earnings do slow down. The inefficiency is that the market tends to underestimate the likelihood and extent of the company's eventual recovery. Once the earnings exceed expectations, the market once again re-rates the company and provides excess returns to the shareholders who bought at the beginning of the process. This works on average, so there are companies that have low expectations and come back to outperform. But there are also many value traps where even the market gets it wrong and their earnings deteriorate even worse than priced. It is here
that we try to find clues of future earnings so we can get rid of value traps and improve on the value factor. This is based off an O'Shaughnessy Asset Management research paper titled "Alpha within Factors" by Jesse Livermore, Chris Meredith, and Patrick O’Shaughnessy
(https://www.osam.com/Commentary/alpha-within-factors).  
In order to accomplish this, there will be three steps:  
1) Create a composite value factor. Instead of just using P/E to find cheap stocks, we will use multiple value factors in order to not over-rely on one factor. We do this by ranking all the stocks on each factor, where a stock in lowest 1% of P/E, will receive rank of 100. If in highest 1%, will receive rank of 1. If missing a score, then assign score of 50. Repeat this for each factor and then add the scores up and take a simple average for the final Value Score. Lastly, we will take the top quintile stocks based off the value score as our starting point. So if we are using the SP500 as an example, we now have 100 stocks with the highest value score. The value factor is composed of:  
     - P/E
     - EV/EBITDA
     - EV/FCF 
     - EV/S  
2) Next we want to attempt to remove value traps. While the following factors are not good predictors of outperformance, they have historically been predictors of dramatic underperformance when ranking in bottom deciles. Because of this, we will rank our top quintile list by each of the following and remove the bottom decile for each one. Keeping with our SP500 example, our list of 100 symbols should go down to around 66 symbols.  
Remove the bottom decile for each scoring:
     - Momentum: trailing 6-months total return (higher is better)
     - Growth: 1yr change in earnings (higher is better)
     - Earnings quality: change in Net Operating Assets (lower is better)
     - Financial Strength: debt to equity (lower is better)
3) Select the top half of this final list based on the value score, equally weight each position


### Factor Rankings  
Ranks a list of stocks based on 4 main factors: Change in Net Operating Assets, One Year Change in Debt, Debt to Equity, and Return on Invested Capital. This section was inspired by and based off of an O'Shaughnessy Asset Management research paper titled "Microcaps — Factor Spreads, Structural Biases, and the Institutional Imperative" by Ehren Stanhope (https://www.osam.com/Commentary/microcaps-factor-spreads-structural-biases-and-the-institutional-imperative). While this was originally for screening quality microcap companies, the functionality has been expanded to factor rank any given list of tickers. 

### Ratios
Calculate numerous ratios for given stocks that can be used for relative valuation. While one can find many of these ratios precalculated somewhere online, it is not clear how those values are calculated making it difficult to compare and have confidence in the figures (e.g. is P/E calculated with trailing twelve months or annual EPS? What do we use for EPS? Basic? Diluted? ExtraOrd items?). The main purpose here is to have full control over how the values are calculated so we can, with confidence, compare these values. The following are currently calculated:  
1. P/E (Price / Earnings)  
     P/E = Share_Price/TTM_EPS  
   Drivers: Payout ratio(dividend), Cost of equity, Expected growth rate  
2. EV/EBITDA (Enterprise Value/Earnings_Before_Interest_Taxes_Depreciation_Amortization)  
     EV = market cap + debt - cash  
     EBITDA = operating income + depreciation/amortization (Currently being used)  
     Drivers: Tax rate, expected growth rate, cost of capital, reinvestment rate  
   EBITDA figures calculated over TTM. Also need subtract any other assets that are not part of EBITDA such as:  
     - minority holding market value of cross holdings, not book value  
     - majority holding: market cap accounts for partial holding but cash, debt, and EBITDA are all   consolidated on balance sheet at 100% (Currently not being accounted for)  
3. P/BV (Price / Book Value)  
   BV = (Total_Equity - Redeemable_Preferred_Shares - Nonredeemable_Preferred_Shares) / Shares  
   This has historically been a very useful ratio to determine cheapness of a stock but as of late, the usefulness might be dwindling. There is a growing portion of stocks that have a negative equity or have what seems to be an expensive P/B ratio but are on the cheaper side when looking at all other ratios. This can be accounted for with some general changes that have been occuring: Increase of intangible assets that are not represented on the balance sheet (e.g. brand name, human capital, advertising, etc), long term assets depreciating faster than their useful lives, and buybacks/dividends that cause decreases in equity when they exceed net income. See more here: https://osam.com/Commentary/negative-equity-veiled-value-and-the-erosion-of-price-to-book   
   Drivers: Return on equity  
4. EV/S (Enterprise Value / Sales)  
   S = TTM_Revenue
   The more common ratio is P/S but this is inconsistent since revenue is to the whole firm and not only the equity owners i.e. market cap. These ratios can be handy if one lacks trust in the assumptions made in the accounting or a company is pre-earnings, hence no P/E.  
   Drivers: Margins
5. EV/FCF (Enterprise Value / Free Cash Flow)

### Moving Average Cross
Given a list of stocks, buy shares when the 50-day moving average crosses the 200-day moving average (golden cross) and sell the shares when 200-day moving average crosses the 50-day moving average (death cross). This is a classic, albeit mostly useless, technical analysis algorithm and was a starting point on this project to get familiarity with IB's APIs.


## Performance
Certain algorithms might take somewhere between 5 to 10 minutes to fully run. This is because whenever we are calculating fundamental ratios such as P/E, we need to request financial statements and it seems from my testing that 2 requests per second will not cause any pacing errors. For this reason, running Alpha Within Factors on SP500 will take around 5 minutes. When requesting just price data or historical data, the algorithm will run much faster as those limits are 100 req/s and 50 req/s, respectively.