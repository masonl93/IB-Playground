import xml.etree.ElementTree as ET


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


    def parseFinancials(self, data):
        '''
        Parses Financial Data

        See sample_financialStatement.xml for coaCodes and their corresponding values
        Input:
            data as xml string from returned from IB's reqFundamentalData
        '''

        # Only initialize non-mandatory values to 0
        # All mandatory keys will be checked to see if they exist before calculating
        latest_val = {'acct_payable': 0, 'accrued_expense': 0, 'others': 0, 'payable': 0, 'deferred':0}
        prev_val = {}

        tree = ET.fromstring(data)
        financial_statements = tree.find('FinancialStatements')
        if len(financial_statements) == 0:
            return None, None
        # financial_statements = [coaMap, annuals, interims]
        # Using annual reports, could switch to interim results for more recent data
        annuals = financial_statements[1]
        latest = annuals[0]
        prev = annuals[1]

        # Pulling values from latest annual report
        if latest.find('.//lineItem[@coaCode="ATOT"]') != None:
            latest_val['total_assets'] = float(latest.find('.//lineItem[@coaCode="ATOT"]').text)
        if latest.find('.//lineItem[@coaCode="ACAE"]') != None:
            # Cash and equivalents
            latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="ACAE"]').text)
        elif latest.find('.//lineItem[@coaCode="ACSH"]') != None:
            # Just cash
            latest_val['cash'] = float(latest.find('.//lineItem[@coaCode="ACSH"]').text)
        if latest.find('.//lineItem[@coaCode="LTLL"]') != None:
            latest_val['total_liabilities'] = float(latest.find('.//lineItem[@coaCode="LTLL"]').text)
        if latest.find('.//lineItem[@coaCode="STLD"]') != None:
            latest_val['total_debt'] = float(latest.find('.//lineItem[@coaCode="STLD"]').text)
        if latest.find('.//lineItem[@coaCode="SOPI"]') != None:
            latest_val['operating_profit'] = float(latest.find('.//lineItem[@coaCode="SOPI"]').text)
        if latest.find('.//lineItem[@coaCode="EIBT"]') != None:
            latest_val['income_b4_taxes'] = float(latest.find('.//lineItem[@coaCode="EIBT"]').text)
        if latest.find('.//lineItem[@coaCode="TTAX"]') != None:
            latest_val['taxes'] = float(latest.find('.//lineItem[@coaCode="TTAX"]').text)
        if latest.find('.//lineItem[@coaCode="RTLR"]') != None:
            latest_val['revenue'] = float(latest.find('.//lineItem[@coaCode="RTLR"]').text)
        if latest.find('.//lineItem[@coaCode="LAPB"]') != None:
            latest_val['acct_payable'] = float(latest.find('.//lineItem[@coaCode="LAPB"]').text)
        if latest.find('.//lineItem[@coaCode="LAEX"]') != None:
            latest_val['accrued_expense'] = float(latest.find('.//lineItem[@coaCode="LAEX"]').text)
        if latest.find('.//lineItem[@coaCode="LPBA"]') != None:
            latest_val['payable'] = float(latest.find('.//lineItem[@coaCode="LPBA"]').text)
        if latest.find('.//lineItem[@coaCode="SBDT"]') != None:
            latest_val['deferred'] = float(latest.find('.//lineItem[@coaCode="SBDT"]').text)
        if latest.find('.//lineItem[@coaCode="SOCL"]') != None:
            latest_val['others'] = float(latest.find('.//lineItem[@coaCode="SOCL"]').text)

        # Pulling values from previous annual report
        if prev.find('.//lineItem[@coaCode="ATOT"]') != None:
            prev_val['total_assets'] = float(prev.find('.//lineItem[@coaCode="ATOT"]').text)
        if prev.find('.//lineItem[@coaCode="SCSI"]') != None:
            prev_val['cash'] = float(prev.find('.//lineItem[@coaCode="SCSI"]').text)
        if prev.find('.//lineItem[@coaCode="LTLL"]') != None:
            prev_val['total_liabilities'] = float(prev.find('.//lineItem[@coaCode="LTLL"]').text)
        if prev.find('.//lineItem[@coaCode="STLD"]') != None:
            prev_val['total_debt'] = float(prev.find('.//lineItem[@coaCode="STLD"]').text)


        return latest_val, prev_val

    
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
