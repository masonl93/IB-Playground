import argparse
import datetime
import math
import scipy.stats


class BlackScholes:
    """
    Black Scholes class for estimating value of warrants and call options.
    If number of shares outstanding AND number of warrants outstanding
    are provided in the constructor, then the dilution from the warrants
    will be taken into consideration.

    Attributes:
        stock_price: Current stock price for the underlying
        strike_price: Exercise price of the warrant
        years: Years until expiration of the warrant
        vol: Volatility or the annualized standard deviation in the stock price
        div: annualized dividend yield
        risk_free_rate: Rate on government bond with maturity closest to expiration date
        shares_out: number of shares outstanding
        warrants_out: number of warrants
    """


    def __init__(self,
                 strike_price,
                 stock_price,
                 risk_free_rate,
                 vol,
                 exp_date,
                 div,
                 shares_out=None,
                 warrants_out=None,
                 warrants_per_share=1):
        """
        BlackScholes Constructor

        Arguments (See above for description):
            strike_price: float
            stock_price: float
            risk_free_rate: float (i.e.: .025)
            vol:  float (i.e.: .30)
            exp_date: Expiration date as str in format: 'mm-dd-yyyy'
            div: float (i.e.: .025)
            shares_out and warrants_out: Float, doesn't have to be exact value,
                the two must match 0's (i.e 30 million shares and 4 millions warrants
                can be passed as (..., 30, 4) or (..., 30000000, 4000000) and all such
                variations)
            warrants_per_share: How many warrants for each share. Defaults to 1 warrant
                for 1 share. If 1 warrant is worth half a share, then you'd pass 2 here.
        """
        self.strike_price = strike_price
        self.stock_price = stock_price
        self.risk_free_rate = risk_free_rate
        self.vol = vol
        exp_date_obj = datetime.datetime.strptime(exp_date, "%m-%d-%Y").date()
        delta = exp_date_obj - datetime.datetime.now().date()
        self.years = delta.days/365.2425
        self.div = div
        self.shares_out = shares_out
        self.warrants_out = warrants_out
        self.warrants_per_share = warrants_per_share


    def calc_d1(self, stock_price, div_adj_intrest_rate, var):
        """
        Notice it is not self.stock_price but rather an argument since
        we need to use this function when having an adjusted stock price
        """
        return (math.log(stock_price/self.strike_price) + \
               (div_adj_intrest_rate + (var/2)) * self.years) \
               / ((var**.5) * (self.years**.5))


    def calc_d2(self, d1):
        return d1 - self.vol * (self.years**.5)


    def dilution_adjustment(self, call_price):
        '''
        Adjusts share price for if the warrants are exercised since
        there will be dilution
        '''
        warrant_count_adj = self.warrants_out/self.warrants_per_share
        return (self.stock_price*self.shares_out + warrant_count_adj*call_price)/ \
               (self.shares_out + warrant_count_adj)



    def price_euro_call(self, vol=None):
        '''
        Returns the value of a European styled Call/Warrant
        '''
        div_adj_intrest_rate = self.risk_free_rate - self.div
        variance = self.vol**2
        d1 = self.calc_d1(self.stock_price, div_adj_intrest_rate, variance)
        d2 = self.calc_d2(d1)
        n_d1 = scipy.stats.norm.cdf(d1)
        n_d2 = scipy.stats.norm.cdf(d2)
        call_price = ((self.stock_price * math.exp(-self.div*self.years)) * n_d1) - \
                     (self.strike_price * math.exp(-self.risk_free_rate*self.years) * n_d2)

        if self.shares_out is not None and self.warrants_out is not None:
            # Adjusting for dilution
            # Loops through adjusting stock price and recalculating call price
            # until we stop making significant progress
            while True:
                last_adj = call_price
                adj_stock_price = self.dilution_adjustment(call_price)
                d1 = self.calc_d1(adj_stock_price, div_adj_intrest_rate, variance)
                d2 = self.calc_d2(d1)
                n_d1 = scipy.stats.norm.cdf(d1)
                n_d2 = scipy.stats.norm.cdf(d2)
                call_price = ((adj_stock_price * math.exp(-self.div*self.years)) * n_d1) - \
                            (self.strike_price * math.exp(-self.risk_free_rate*self.years) * n_d2)
                # print(call_price)
                if round(call_price, 2) == round(last_adj, 2):
                    break
            print('Black Scholes calculation WITH share dilution:')
            return call_price
        else:
            print('Black Scholes calculation with no share dilution:')
            return call_price/self.warrants_per_share


def main(args):
    bs = BlackScholes(args.strike, args.stock, args.risk, args.vol,
                      args.date, args.div, args.shares_out, args.warrants_out,
                      args.warrants_per_share)
    print('$' + str(round(bs.price_euro_call(), 5)))
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate the value of a European-styled Warrant/Call Option')
    parser.add_argument('-k', '--strike', type=float, help='Strike Price', required=True)
    parser.add_argument('-s', '--stock',  type=float, help='Current Stock Price', required=True)
    parser.add_argument('-r', '--risk', type=float, help='Risk Free Rate', required=True)
    parser.add_argument('-v', '--vol', type=float, help='Volatility', required=True)
    parser.add_argument('-d', '--date',  help='Date of expiration in mm-dd-yyyy format', required=True)
    parser.add_argument('-y', '--div', type=float, help='Yearly Dividend Yield', required=True)
    parser.add_argument('--shares_out', type=float, help='Shares Outstanding')
    parser.add_argument('--warrants_out', type=float, help='Warrants Outstanding')
    parser.add_argument('--warrants_per_share', type=float, help='How many Warrants per Share', default=1)
    main(parser.parse_args())


# TODO ##################
'''
- allow vol to be list of values or range?

- write simple tests (expected values for certain inputs)

- Create jupyter nb demoing functionality. Plug in different vol's and
make some nice graphics. Demo how dilution alters value

- Address BS weaknesses, look up academia articles for possible solutions
and implement

'''
#########################