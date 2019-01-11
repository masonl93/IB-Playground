import pandas



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


def calcTotalReturn(start, end, dividends):
    return (end - start + dividends)/start


def compositeValueRank(df):
    '''
    Ranks a pandas.dataframe by Composite Value

    Input: Dataframe with following columns:
        - P/E
        - EV/EBITDA
        - EV/S
        - EV/FCF
    Output: Dataframe same as input but with new columns scoring each value factor 0 to 100
        A row with a P/E in the lowest percentile will get a P/E Score of 100, and with a
        EV/S in the highest percentile will get a EV/S Score of 0, and so on. Any column that
        does not have a value (i.e. a company with no EPS will not have a P/E) will get an average
        score of 50. The final column is the Value Score which is a simple average of the 4 other scores
    '''
    df['P/E Score'] = None
    df['EV/EBITDA Score'] = None
    df['EV/S Score'] = None
    df['EV/FCF Score'] = None
    df['Value Score'] = None

    # P/E Score
    # Note: Need to check column type as pandas.dataframe throws exception
    # when comparing different type such as str and float. If a column
    # has a mix of floats and str, then the column type is object i.e.
    # we know that we are missing some values and we can check if values
    # are 'N/A'. If not object type, then we know there's no missing values
    if df['P/E'].dtype == 'object':
        df_missing = df[df['P/E'].isnull()]
        df_good = df[df['P/E'].notnull()]
        for i, row in df_missing.iterrows():
            df.at[i, 'P/E Score'] = 50
        for i, row in df_good.iterrows():
            df.at[i, 'P/E Score'] = 100 - pandas.qcut(df_good['P/E'], 100, labels=False)[i]
    else:
        for i, row in df.iterrows():
            df.at[i, 'P/E Score'] = 100 - pandas.qcut(df['P/E'], 100, labels=False)[i]

    # EV/EBITDA Score
    if df['EV/EBITDA'].dtype == 'object':
        df_missing = df[df['EV/EBITDA'].isnull()]
        df_good = df[df['EV/EBITDA'].notnull()]
        for i, row in df_missing.iterrows():
            df.at[i, 'EV/EBITDA Score'] = 50
        for i, row in df_good.iterrows():
            df.at[i, 'EV/EBITDA Score'] = 100 - pandas.qcut(df_good['EV/EBITDA'], 100, labels=False)[i]
    else:
        for i, row in df.iterrows():
            df.at[i, 'EV/EBITDA Score'] = 100 - pandas.qcut(df['EV/EBITDA'], 100, labels=False)[i]

    # EV/S Score
    if df['EV/S'].dtype == 'object':
        df_missing = df[df['EV/S'].isnull()]
        df_good = df[df['EV/S'].notnull()]
        for i, row in df_missing.iterrows():
            df.at[i, 'EV/S Score'] = 50
        for i, row in df_good.iterrows():
            df.at[i, 'EV/S Score'] = 100 - pandas.qcut(df_good['EV/S'], 100, labels=False)[i]
    else:
        for i, row in df.iterrows():
            df.at[i, 'EV/S Score'] = 100 - pandas.qcut(df['EV/S'], 100, labels=False)[i]


    # EV/FCF Score
    if df['EV/FCF'].dtype == 'object':
        df_missing = df[df['EV/FCF'].isnull()]
        df_good = df[df['EV/FCF'].notnull()]
        for i, row in df_missing.iterrows():
            df.at[i, 'EV/FCF Score'] = 50
        for i, row in df_good.iterrows():
            df.at[i, 'EV/FCF Score'] = 100 - pandas.qcut(df_good['EV/FCF'], 100, labels=False)[i]
    else:
        for i, row in df.iterrows():
            df.at[i, 'EV/FCF Score'] = 100 - pandas.qcut(df['EV/FCF'], 100, labels=False)[i]

    # Value Score
    for i, row in df.iterrows():
        df.at[i, 'Value Score'] = (row['P/E Score'] + row['EV/EBITDA Score'] + row['EV/S Score'] + row['EV/FCF Score'])/4

    df = df.sort_values('Value Score', ascending=False)
    return df




def calcNOA(data):
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

    if data and all(var in data for var in noa_vars):
        return (data['total_assets'] - data['cash'] -
                    data['total_liabilities'] - data['total_debt'])
    else:
        return None


def calcDebtChange(debt, prev_debt):
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


def calcROIC(data):
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
