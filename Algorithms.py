

def movingAvgCross(df):
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


class Factors():
    def __init__(self):
        pass


    def calcNOA(self, data):
        '''
        Calculating Net Opearating Assets
        NOA = OA - OL
        operating assets = total assets - Cash and Short Term Investments
        operating liabilites = total liabilities - Total debt

        Input:
            dict containing necessary keys for computing (see noa_vars)
        Output:
            None if data is missing keys needed to compute NOA
            else NOA as a float
        '''
        noa_vars = ['total_assets', 'cash', 'total_liabilities', 'total_debt']

        if all(var in data for var in noa_vars):
            return (data['total_assets'] - data['cash'] -
                     data['total_liabilities'] - data['total_debt'])
        else:
            return None


    def calcDebtChange(self, debt, prev_debt):
        '''
        Calculates the change between two periods of debt

        Output:
            If previous debt is 0 and current debt is > 0, then we
            return "Divide by Zero" as a string
            Else return a float
        '''
        if prev_debt == 0:
            if debt != 0:
                return "Divide by Zero"
            else:
                return 0
        else:
            return ((debt - prev_debt)/prev_debt)


    def calcROIC(self, data):
        '''
        Calculating ROIC
        ROIC = NOPAT/IC
        NOPAT = Operating Profit * (1-tax_rate)
        Tax_rate = income taxes/net income before taxes
        IC = Total Assets - Non-interest bearing current liabilities - Excess cash
        NIBCL = accounts payable + accrued expenses + other current liabilities +
                accrued/payable + deferred income
        Excess cash = Cash & Equivalents - required_cash
        required_cash = .025*revenue

        Input:
            dict containing necessary keys for computing (see roic_vars)
        Output:
            None if data is missing keys needed to compute ROIC
            else ROIC as a float
        '''
        roic_vars = ['operating_profit', 'income_b4_taxes', 'total_assets', 'cash', 'revenue']

        if all(var in data for var in roic_vars):
            if 'taxes' in data:
                tax_rate = data['taxes']/data['income_b4_taxes']
                nopat = data['operating_profit']*(1-tax_rate)
            else:
                nopat = data['operating_profit']
            # TODO: Make this calculation smarter
            excess_cash = data['cash'] - .025*data['revenue']
            nibcl = (data['acct_payable'] + data['accrued_expense'] +
                        data['others'] + data['payable'] + data['deferred'])
            invested_cap = data['total_assets'] - nibcl - excess_cash
            return (nopat/invested_cap)
        else:
            print('Cannot calc ROIC. Missing values:')
            print(set(roic_vars).difference(data))
            return None
