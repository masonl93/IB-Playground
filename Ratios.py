


class Ratio():
    '''
    Class for calculating various ratios

    Many of the functions take dictionaries as input, which can easily be
    retrieved from TestApp.parseFinancials()
    '''
    def __init__(self):
        pass

    '''
    Calculates Market Cap, Firm Value, and Enterprise Value

    Input:
        price: Stock's price as float
        data: dict containing the keys:
            - shares
            - total_debt
            - cash_investments or cash
    '''
    def getCompanyValues(self, price, data):
        mkt_cap = price*data['shares']
        firm_val = mkt_cap + data['total_debt']
        if 'cash_investments' in data:
            ev = firm_val - data['cash_investments']
        else:
            ev = firm_val - data['cash']

        return mkt_cap, firm_val, ev


    '''
    Calculates TTM P/E Ratio

    Input:
        price: Stock's price as float
        qtr1, qtr2, qtr3, qtr4: dict containing the key:
            - eps
    '''
    def getP_E(self, price, qtr1, qtr2, qtr3, qtr4):
        ttm_eps = qtr1['eps'] + qtr2['eps'] + qtr3['eps'] + qtr4['eps']
        if ttm_eps <= 0:
            return 'N/A'
        else:
            return price/ttm_eps


    '''
    Calculates TTM EV/EBITDA Ratio

    Input:
        ev: Stock's enterprise value
        qtr1, qtr2, qtr3, qtr4: dict containing the keys:
            - op_income
            - dep_amor
    '''
    def getEV_EBITDA(self, ev, qtr1, qtr2, qtr3, qtr4):
        if 'op_income' not in qtr1:
            # No operating income on income statement, probably a bank
            return 'N/A'
        ebitda = qtr1['op_income'] + qtr1['dep_amor'] + qtr2['op_income'] + qtr2['dep_amor'] + qtr3['op_income'] + qtr3['dep_amor'] + qtr4['op_income'] + qtr4['dep_amor']
        if ebitda <= 0:
            return 'N/A'
        else:
            return ev / ebitda


    '''
    Calculates P/B Ratio

    Input:
        price: Stock's price as float
        qtr1: dict containing the key:
            - total_equity
            - redeemable_preferred andf preferred if present
    '''
    def getP_B(self, price, qtr1):
        bv = qtr1['total_equity']
        if 'redeemable_preferred' in qtr1:
            bv = bv - qtr1['redeemable_preferred']
        if 'preferred' in qtr1:
            bv = bv - qtr1['preferred']
        bv_per_share = bv/float(qtr1['shares'])
        return price/bv_per_share


    '''
    Calculates TTM EV/Sales Ratio

    Input:
        ev: Stock's enterprise value
        qtr1, qtr2, qtr3, qtr4: dict containing the key:
            - revenue
    '''
    def getEV_S(self, ev, qtr1, qtr2, qtr3, qtr4):
        if 'revenue' not in qtr1:
            # No revenue on income statement, probably a bank
            return 'N/A'
        ttm_rev = qtr1['revenue'] + qtr2['revenue'] + qtr3['revenue'] + qtr4['revenue']
        if ttm_rev <= 0:
            return 'N/A'
        else:
            return ev / ttm_rev


    '''
    Calculates TTM EV/FCF Ratio

    Input:
        ev: Stock's enterprise value
        qtr1, qtr2, qtr3, qtr4: dict containing the key:
            - op_cash_flow
            - capex
    '''
    def getEV_FCF(self, ev, qtr1, qtr2, qtr3, qtr4):
        ttm_cf = qtr1['op_cash_flow'] + qtr2['op_cash_flow'] + qtr3['op_cash_flow'] + qtr4['op_cash_flow']
        ttm_capex = qtr1['capex'] + qtr2['capex'] + qtr3['capex'] + qtr4['capex']
        ttm_fcf = ttm_cf + ttm_capex
        if ttm_fcf <= 0:
            return 'N/A'
        else:
            return ev / ttm_fcf
