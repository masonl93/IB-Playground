'''
Functions for calculating various ratios

Many of the functions take dictionaries as input, which can easily be
retrieved from TestApp.parseFinancials()
'''



'''
Calculates Market Cap, Firm Value, and Enterprise Value

Input:
    price: Stock's price as float
    data: dict containing any of the keys:
        - total_common_shares_outstanding
        - total_debt
        - minority_interest
        - cash&equivalents
        - cash

    TODO: Include preferred equity as a debt, associate company at market value as cash
'''
def getCompanyValues(price, data):
    mkt_cap = None
    firm_val = None
    ev = None
    if data and 'total_common_shares_outstanding' in data:
        mkt_cap = price*data['total_common_shares_outstanding']

        # debts
        if 'total_debt' in data:
            firm_val = mkt_cap + data['total_debt']
        else:
            firm_val = mkt_cap
        if 'minority_interest' in data:
            firm_val += data['minority_interest']

        # cash
        if 'cash&equivalents' in data:
            ev = firm_val - data['cash&equivalents']
        elif 'cash' in data:
            ev = firm_val - data['cash']
        else:
            ev = firm_val
    return mkt_cap, firm_val, ev


'''
Calculates TTM P/E Ratio

Input:
    price: Stock's price as float
    qtr1, qtr2, qtr3, qtr4: dict containing the key:
        - diluted_eps_excluding_extraord_items
'''
def getP_E(price, qtr1, qtr2, qtr3, qtr4):
    ttm_eps = 0
    if qtr1 and 'diluted_eps_excluding_extraord_items' in qtr1:
        ttm_eps += qtr1['diluted_eps_excluding_extraord_items']
    if qtr2 and 'diluted_eps_excluding_extraord_items' in qtr2:
        ttm_eps += qtr2['diluted_eps_excluding_extraord_items']
    if qtr3 and 'diluted_eps_excluding_extraord_items' in qtr3:
        ttm_eps += qtr3['diluted_eps_excluding_extraord_items']
    if qtr4 and 'diluted_eps_excluding_extraord_items' in qtr4:
        ttm_eps += qtr4['diluted_eps_excluding_extraord_items']

    if ttm_eps <= 0:
        return None
    else:
        return price/ttm_eps


'''
Calculates TTM EV/EBITDA Ratio

Input:
    ev: Stock's enterprise value
    qtr1, qtr2, qtr3, qtr4: dict containing the keys:
        - operating_income
        - depreciation/amortization
        - depreciation/depletion
        - amortization
'''
def getEV_EBITDA(ev, qtr1, qtr2, qtr3, qtr4):
    ebitda = 0
    if ev:
        # EBITDA
        if qtr1 and 'operating_income' in qtr1:
            ebitda += qtr1['operating_income']
            if 'depreciation/amortization' in qtr1:
                ebitda += qtr1['depreciation/amortization']
            elif 'depreciation/depletion' in qtr1:
                ebitda += qtr1['depreciation/depletion']
            elif 'amortization' in qtr1:
                ebitda += qtr1['amortization']
        if qtr2 and 'operating_income' in qtr2:
            ebitda += qtr2['operating_income']
            if 'depreciation/amortization' in qtr2:
                ebitda += qtr2['depreciation/amortization']
            elif 'depreciation/depletion' in qtr2:
                ebitda += qtr2['depreciation/depletion']
            elif 'amortization' in qtr2:
                ebitda += qtr2['amortization']
        if qtr3 and 'operating_income' in qtr3:
            ebitda += qtr3['operating_income']
            if 'depreciation/amortization' in qtr3:
                ebitda += qtr3['depreciation/amortization']
            elif 'depreciation/depletion' in qtr3:
                ebitda += qtr3['depreciation/depletion']
            elif 'amortization' in qtr3:
                ebitda += qtr3['amortization']
        if qtr4 and 'operating_income' in qtr4:
            ebitda += qtr4['operating_income']
            if 'depreciation/amortization' in qtr4:
                ebitda += qtr4['depreciation/amortization']
            elif 'depreciation/depletion' in qtr4:
                ebitda += qtr4['depreciation/depletion']
            elif 'amortization' in qtr4:
                ebitda += qtr4['amortization']
    if ebitda <= 0:
        return None
    else:
        return ev / ebitda


'''
Calculates P/B Ratio

Input:
    price: Stock's price as float
    qtr1: dict containing the key:
        - total_equity
        - total_common_shares_outstanding
        - redeemable_preferred_stock
        - preferred_stock_non_redeemable
'''
def getP_B(price, qtr1):
    bv = 0
    if qtr1 and 'total_equity' in qtr1 and 'total_common_shares_outstanding' in qtr1:
        bv = qtr1['total_equity']
        if 'redeemable_preferred_stock' in qtr1:
            bv = bv - qtr1['redeemable_preferred_stock']
        if 'preferred_stock_non_redeemable' in qtr1:
            bv = bv - qtr1['preferred_stock_non_redeemable']
        bv_per_share = bv/float(qtr1['total_common_shares_outstanding'])
    if bv_per_share <= 0:
        return None
    else:
        return price/bv_per_share


'''
Calculates TTM EV/Sales Ratio

Input:
    ev: Stock's enterprise value
    qtr1, qtr2, qtr3, qtr4: dict containing the key:
        - total_revenue
'''
def getEV_S(ev, qtr1, qtr2, qtr3, qtr4):
    ttm_rev = 0
    if ev:
        if qtr1 and 'total_revenue' in qtr1:
            ttm_rev += qtr1['total_revenue']
        if qtr2 and 'total_revenue' in qtr2:
            ttm_rev += qtr2['total_revenue']
        if qtr3 and 'total_revenue' in qtr3:
            ttm_rev += qtr3['total_revenue']
        if qtr4 and 'total_revenue' in qtr4:
            ttm_rev += qtr4['total_revenue']
    if ttm_rev <= 0:
        return None
    else:
        return ev / ttm_rev


'''
Calculates TTM EV/FCF Ratio

Input:
    ev: Stock's enterprise value
    qtr1, qtr2, qtr3, qtr4: dict containing the key:
        - net_income
        - depreciation/depletion
        - amortization
        - total_cash_dividends_paid
        - capital_expenditures

cash flow = net_income + depreciation/depletion (TODO: add other non cash expenses)
fcf = cash flow - capex - dividends (TODO: subtract preferred dividends also)
'''
def getEV_FCF(ev, qtr1, qtr2, qtr3, qtr4):
    ttm_fcf = 0
    if ev:
        if qtr1 and 'net_income' in qtr1:
            ttm_fcf += qtr1['net_income']
            if 'depreciation/depletion' in qtr1:
                ttm_fcf += qtr1['depreciation/depletion']
            if 'amortization' in qtr1:
                ttm_fcf += qtr1['amortization']
            if 'capital_expenditures' in qtr1:
                ttm_fcf -= qtr1['capital_expenditures']
            if 'total_cash_dividends_paid' in qtr1:
                ttm_fcf -= qtr1['total_cash_dividends_paid']
        if qtr2 and 'net_income' in qtr2:
            ttm_fcf += qtr2['net_income']
            if 'depreciation/depletion' in qtr2:
                ttm_fcf += qtr2['depreciation/depletion']
            if 'amortization' in qtr2:
                ttm_fcf += qtr2['amortization']
            if 'capital_expenditures' in qtr2:
                ttm_fcf -= qtr2['capital_expenditures']
            if 'total_cash_dividends_paid' in qtr2:
                ttm_fcf -= qtr2['total_cash_dividends_paid']
        if qtr3 and 'net_income' in qtr3:
            ttm_fcf += qtr3['net_income']
            if 'depreciation/depletion' in qtr3:
                ttm_fcf += qtr3['depreciation/depletion']
            if 'amortization' in qtr3:
                ttm_fcf += qtr3['amortization']
            if 'capital_expenditures' in qtr3:
                ttm_fcf -= qtr3['capital_expenditures']
            if 'total_cash_dividends_paid' in qtr3:
                ttm_fcf -= qtr3['total_cash_dividends_paid']
        if qtr4 and 'net_income' in qtr4:
            ttm_fcf += qtr4['net_income']
            if 'depreciation/depletion' in qtr4:
                ttm_fcf += qtr4['depreciation/depletion']
            if 'amortization' in qtr4:
                ttm_fcf += qtr4['amortization']
            if 'capital_expenditures' in qtr4:
                ttm_fcf -= qtr4['capital_expenditures']
            if 'total_cash_dividends_paid' in qtr4:
                ttm_fcf -= qtr4['total_cash_dividends_paid']
    if ttm_fcf <= 0:
        return None
    else:
        return ev / ttm_fcf


'''
Calculates how much dividends per share were paid out

qtr3 and qtr4 default to None since this function can
be used to calculate last 2 quarters dividend
payout for total return over 6 months or 12 months
if last two args are provided

Input:
    qtr1, qtr2, qtr3, qtr4: dict containing the key:
        - dps_common_stock_primary_issue
'''
def getDivPayout(qtr1, qtr2, qtr3=None, qtr4=None):
    div = 0
    if qtr1 and 'dps_common_stock_primary_issue' in qtr1:
        div += qtr1['dps_common_stock_primary_issue']
    if qtr2 and 'dps_common_stock_primary_issue' in qtr2:
        div += qtr2['dps_common_stock_primary_issue']
    if qtr3 and 'dps_common_stock_primary_issue' in qtr3:
        div += qtr3['dps_common_stock_primary_issue']
    if qtr4 and 'dps_common_stock_primary_issue' in qtr4:
         div += qtr4['dps_common_stock_primary_issue']
    return div


def calcChangeInNOA(annual, prev_annual):
    '''
    Calculating Change in Net Opearating Assets
    NOA = OA - OL
    operating assets = total_assets - short_term_investments - long_term_investments
    operating liabilites = total_liabilities - notes_payable/short_term_debt -
                            current_port_of_lt_debt/capital_leases - total_long_term_debt
    TODO: missing any other non-operating values here?

    Input:
        Current and previous annual reports: dicts w/ keys:
            - total_assets
            - short_term_investments
            - long_term_investments
            - total_liabilities
            - notes_payable/short_term_debt
            - current_port_of_lt_debt/capital_leases
            - total_long_term_debt
    '''
    oa = None
    ol = None
    noa = None
    noa_prev = None
    if annual and prev_annual:
        # Current NOA
        if 'total_assets' in annual:
            oa = annual['total_assets']
            if 'short_term_investments' in annual:
                oa -= annual['short_term_investments']
            if 'long_term_investments' in annual:
                oa -= annual['long_term_investments']
        if 'total_liabilities' in annual:
            ol = annual['total_liabilities']
            if 'notes_payable/short_term_debt' in annual:
                ol -= annual['notes_payable/short_term_debt']
            if 'current_port_of_lt_debt/capital_leases' in annual:
                ol -= annual['current_port_of_lt_debt/capital_leases']
            if 'total_long_term_debt' in annual:
                ol -= annual['total_long_term_debt']
        if oa and ol:
            noa = oa - ol

        # Previous NOA
        oa = None
        ol = None
        if 'total_assets' in prev_annual:
            oa = prev_annual['total_assets']
            if 'short_term_investments' in prev_annual:
                oa -= prev_annual['short_term_investments']
            if 'long_term_investments' in prev_annual:
                oa -= prev_annual['long_term_investments']
        if 'total_liabilities' in prev_annual:
            ol = prev_annual['total_liabilities']
            if 'notes_payable/short_term_debt' in prev_annual:
                ol -= prev_annual['notes_payable/short_term_debt']
            if 'current_port_of_lt_debt/capital_leases' in prev_annual:
                ol -= prev_annual['current_port_of_lt_debt/capital_leases']
            if 'total_long_term_debt' in prev_annual:
                ol -= prev_annual['total_long_term_debt']
        if oa and ol:
            noa_prev = oa - ol

        # 1yr change in NOA
        if noa and noa_prev:
            return (noa - noa_prev)/noa_prev
    return None


'''
Calculate the 1 year growth of EPS

Input:
    Current and previous annual reports: dicts w/ keys:
        - diluted_eps_excluding_extraord_items
'''
def calcOneYearGrowth(annual, prev_annual):
    if (annual and 'diluted_eps_excluding_extraord_items' in annual
         and prev_annual and 'diluted_eps_excluding_extraord_items' in prev_annual):
        eps = annual['diluted_eps_excluding_extraord_items']
        prev_eps = prev_annual['diluted_eps_excluding_extraord_items']
        return ((eps - prev_eps)/abs(prev_eps))
    return None


def calcDebtToEquity(data):
    '''
    Calculating Debt to Equity Ratio
    debt_to_equity = total liabilites / total equity

    Alternatives: Can use reqMktData with tick type 258 to get IB's version of debt to equity
    or could use total debt instead of total liabilities

    Input:
        latest quarterly data: dict w/ keys:
            - total_liabilities
            - total_equity
    '''
    if data and 'total_liabilities' in data and 'total_equity' in data:
        return (data['total_liabilities']/data['total_equity'])
    else:
        return None


def calcDebtChange(annual, prev_annual):
    '''
    Calculates the change between two periods of debt

    Input:
        Two reports as dicts w/ keys:
            - total_debt
    '''
    if annual and annual['total_debt'] and prev_annual and prev_annual['total_debt']:
        # Checking for divide by zero
        if prev_annual['total_debt'] != 0:
            return ((annual['total_debt'] - prev_annual['total_debt'])/prev_annual['total_debt'])
        elif annual['total_debt'] == 0:
            return 0.0
    return None


def calcROIC(qtr1, qtr2, qtr3, qtr4):
    '''
    Calculating ROIC

    ROIC = NOPAT/avg(IC)
    NOPAT = operating_income * (1-tax_rate)
    IC = total_long_term_debt + current_port_of_lt_debt/capital_leases +
         notes_payable/short_term_debt + minority_interest + total_equity - cash

    Input:
        qtr1, qtr2, qtr3, qtr4: dict containing the keys:
            - operating_income
            - net_income_before_taxes
            - net_income_after_taxes
            - total_long_term_debt
            - current_port_of_lt_debt/capital_leases
            - notes_payable/short_term_debt
            - minority_interest
            - total_equity
            - cash_and_short_term_investments or cash&equivalents or cash
    '''
    ic1 = 0
    ic2 = 0
    nopat = 0
    if qtr1 and qtr2 and qtr1['operating_income'] and qtr1['net_income_before_taxes'] and qtr1['net_income_after_taxes']:
        # Net Operating Profit after Taxes for TTM
        tax_rate = (qtr1['net_income_before_taxes'] - qtr1['net_income_after_taxes']) / qtr1['net_income_before_taxes']
        nopat = qtr1['operating_income'] * (1 - tax_rate)

        if qtr2 and qtr2['operating_income'] and qtr2['net_income_before_taxes'] and qtr2['net_income_after_taxes']:
            tax_rate = (qtr2['net_income_before_taxes'] - qtr2['net_income_after_taxes']) / qtr2['net_income_before_taxes']
            nopat += qtr2['operating_income'] * (1 - tax_rate)

        if qtr3 and qtr3['operating_income'] and qtr3['net_income_before_taxes'] and qtr3['net_income_after_taxes']:
            tax_rate = (qtr3['net_income_before_taxes'] - qtr3['net_income_after_taxes']) / qtr3['net_income_before_taxes']
            nopat += qtr3['operating_income'] * (1 - tax_rate)

        if qtr4 and qtr4['operating_income'] and qtr4['net_income_before_taxes'] and qtr4['net_income_after_taxes']:
            tax_rate = (qtr4['net_income_before_taxes'] - qtr4['net_income_after_taxes']) / qtr4['net_income_before_taxes']
            nopat += qtr4['operating_income'] * (1 - tax_rate)

        # Invested Capital last qtr
        if 'total_long_term_debt' in qtr1:
            ic1 += qtr1['total_long_term_debt']
        if 'current_port_of_lt_debt/capital_leases' in qtr1:
            ic1 += qtr1['current_port_of_lt_debt/capital_leases']
        if 'notes_payable/short_term_debt' in qtr1:
            ic1 += qtr1['notes_payable/short_term_debt']
        if 'minority_interest' in qtr1:
            ic1 += qtr1['minority_interest']
        if 'total_equity' in qtr1:
            ic1 += qtr1['total_equity']
        if 'cash_and_short_term_investments' in qtr1:
            ic1 -= qtr1['cash_and_short_term_investments']
        elif 'cash&equivalents' in qtr1:
            ic1 -= qtr1['cash&equivalents']
        elif 'cash' in qtr1:
            ic1 -= qtr1['cash']

        # Invested Capital two qtr ago
        if 'total_long_term_debt' in qtr2:
            ic2 += qtr2['total_long_term_debt']
        if 'current_port_of_lt_debt/capital_leases' in qtr2:
            ic2 += qtr2['current_port_of_lt_debt/capital_leases']
        if 'notes_payable/short_term_debt' in qtr2:
            ic2 += qtr2['notes_payable/short_term_debt']
        if 'minority_interest' in qtr2:
            ic2 += qtr2['minority_interest']
        if 'total_equity' in qtr2:
            ic2 += qtr2['total_equity']
        if 'cash_and_short_term_investments' in qtr2:
            ic2 -= qtr2['cash_and_short_term_investments']
        elif 'cash&equivalents' in qtr2:
            ic2 -= qtr2['cash&equivalents']
        elif 'cash' in qtr2:
            ic2 -= qtr2['cash']

        # Average Invested Capital over last 2 qtrs
        ic = (ic1 + ic2) / 2

        # Ensure we don't have an operating loss and negative invested capital
        if (ic < 0 and nopat >= 0) or ic > 0:
            return nopat/ic
    return None
