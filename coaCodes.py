coaCode_map = {# INC
           'SREV': 'revenue',
           'SORE': 'other_revenue',
           'RTLR': 'total_revenue',
           'SCOR': 'cost_of_revenue',
           'SGRP': 'gross_profit',
           'SSGA': 'selling/general/admin._expenses',
           'ERAD': 'research&development',
           'SDPR': 'depreciation/amortization',
           'SINN': 'interest_exp',
           'SUIE': 'unusual_expense',
           'SOOE': 'other_operating_expenses',
           'ETOE': 'total_operating_expense',
           'SOPI': 'operating_income',
           'SNIN': 'interest_inc_net-non-op',
           'NGLA': 'gain_on_sale_of_assets',
           'SONT': 'other',
           'EIBT': 'net_income_before_taxes',
           'TTAX': 'provision_for_income_taxes',
           'TIAT': 'net_income_after_taxes',
           'CMIN': 'minority_interest',
           'CEIA': 'equity_in_affiliates',
           'CGAP': 'gaap_adjustment',
           'NIBX': 'net_income_before_extra_items',
           'STXI': 'total_extraordinary_items',
           'NINC': 'net_income',
           'SANI': 'total_adjustments_to_net_income',
           'CIAC': 'income_available_to_com_excl_extraord',
           'XNIC': 'income_available_to_com_incl_extraord',
           'SDAJ': 'dilution_adjustment',
           'SDNI': 'diluted_net_income',
           'SDWS': 'diluted_weighted_average_shares',
           'SDBF': 'diluted_eps_excluding_extraord_items',
           'DDPS1': 'dps_common_stock_primary_issue',
           'VDES': 'diluted_normalized_eps',
           'SPRE': 'total_premiums_earned',
           'RNII': 'net_investment_income',
           'RRGL': 'realized&unrealized_gains',
           'SLBA': 'losses_benefits_adjustments',
           'EPAC': 'amortization_of_policy_acquisition_costs',
           'SNIE': 'non-interest_expense_bank',
           'SNII': 'non-interest_income_bank',
           'SIAP': 'net_interest_inc_after_loan_loss_prov',
           'ELLP': 'loan_loss_provision',
           'ENII': 'net_interest_income',
           'STIE': 'total_interest_expense',
           'SIIB': 'interest_income_bank',
           'EDOE': 'operations&maintenance',
           'EFEX': 'fuel_expense',
           'NAFC': 'allowance_for_funds_used_during_const',
           # BAL
           'ACSH': 'cash',
           'ACAE': 'cash&equivalents',
           'ASTI': 'short_term_investments',
           'SCSI': 'cash_and_short_term_investments',
           'AACR': 'accounts_receivable',
           'ATRC': 'total_receivables',
           'AITL': 'total_inventory',
           'APPY': 'prepaid_expenses',
           'SOCA': 'other_current_assets',
           'ATCA': 'total_current_assets',
           'APTC': 'property/plant/equipment_gross',
           'ADEP': 'accumulated_depreciation',
           'APPN': 'property/plant/equipment_net',
           'AGWI': 'goodwill',
           'AINT': 'intangibles',
           'SINV': 'long_term_investments',
           'ALTR': 'note_receivable_long_term',
           'SOLA': 'other_long_term_assets',
           'SOAT': 'other_assets',
           'ATOT': 'total_assets',
           'LAPB': 'accounts_payable',
           'LPBA': 'payable/accrued',
           'LAEX': 'accrued_expenses',
           'LSTD': 'notes_payable/short_term_debt',
           'LCLD': 'current_port_of_lt_debt/capital_leases',
           'SOCL': 'other_current_liabilities',
           'LTCL': 'total_current_liabilities',
           'LLTD': 'long_term_debt',
           'LCLO': 'capital_lease_obligations',
           'LTTD': 'total_long_term_debt',
           'STLD': 'total_debt',
           'SBDT': 'deferred_income_tax',
           'LMIN': 'minority_interest',
           'SLTL': 'other_liabilities',
           'LTLL': 'total_liabilities',
           'SRPR': 'redeemable_preferred_stock',
           'SPRS': 'preferred_stock_non_redeemable',
           'SCMS': 'common_stock',
           'QPIC': 'additional_paid-in_capital',
           'QRED': 'retained_earnings',
           'QTSC': 'treasury_stock',
           'QEDG': 'esop_debt_guarantee',
           'QUGL': 'unrealized_gain',
           'SOTE': 'other_equity',
           'QTLE': 'total_equity',
           'QTEL': 'total_liabilities&shareholders_equity',
           'QTCO': 'total_common_shares_outstanding',
           'QTPO': 'total_preferred_shares_outstanding',
           'STBP': 'tangible_book_value_per_share',
           'APRE': 'insurance_receivables',
           'ADPA': 'deferred_policy_acquisition_costs',
           'SPOL': 'policy_liabilities',
           'LSTB': 'total_short_term_borrowings',
           'SOBL': 'other_bearing_liabilities',
           'LDBT': 'total_deposits',
           'ANTL': 'net_loans',
           'SOEA': 'other_earning_assets',
           'ACDB': 'cash&due_from_banks',
           'SUPN': 'total_utility_plant',
           # CAS
           'ONET': 'net_income/starting_line',
           'SDED': 'depreciation/depletion',
           'SAMT': 'amortization',
           'OBDT': 'deferred_taxes',
           'SNCI': 'non-cash_items',
           'SOCF': 'changes_in_working_capital',
           'OTLO': 'cash_from_operating_activities',
           'SCEX': 'capital_expenditures',
           'SICF': 'other_investing_cash_flow_items',
           'ITLI': 'cash_from_investing_activities',
           'SFCF': 'financing_cash_flow_items',
           'FCDP': 'total_cash_dividends_paid',
           'FPSS': 'issuance_of_stock',
           'FPRD': 'issuance_of_debt',
           'FTLF': 'cash_from_financing_activities',
           'SFEE': 'foreign_exchange_effects',
           'SNCC': 'net_change_in_cash',
           'SCIP': 'cash_interest_paid',
           'SCTP': 'cash_taxes_paid',
           'OCRC': 'cash_receipts',
           'OCPD': 'cash_payments',
}
