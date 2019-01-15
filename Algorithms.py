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
