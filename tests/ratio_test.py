import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Ratios
import pytest


class Test_GetCompanyValues(object):
    @pytest.fixture
    def setup(self):
        data = {'total_common_shares_outstanding': 100,
                 'total_debt': 50,
                 'minority_interest': 2,
                 'cash&equivalents': 8,
                 'cash': 5}
        return data

    def test_getCompanyValues(self, setup):
        data = setup
        price = 10.0
        assert Ratios.getCompanyValues(price, data) == (1000, 1052, 1044)

    def test_getCompanyValues_None(self):
        price = 10.0
        assert Ratios.getCompanyValues(price, None) == (None, None, None)

    def test_getCompanyValues_SharesMissing(self, setup):
        data = setup
        price = 10.0
        del data['total_common_shares_outstanding']
        assert Ratios.getCompanyValues(price, data) == (None, None, None)

    def test_getCompanyValues_noDebt(self, setup):
        data = setup
        price = 10.0
        del data['total_debt']
        del data['minority_interest']
        assert Ratios.getCompanyValues(price, data) == (1000, 1000, 992)

    def test_getCompanyValues_noCashEq(self, setup):
        data = setup
        price = 10.0
        del data['cash&equivalents']
        assert Ratios.getCompanyValues(price, data) == (1000, 1052, 1047)


class Test_GetP_E(object):
    @pytest.fixture
    def setup(self):
        qtr1 = {'diluted_eps_excluding_extraord_items': 1}
        qtr2 = qtr1
        qtr3 = qtr1
        qtr4 = qtr1
        return qtr1, qtr2, qtr3, qtr4

    def test_getP_E_None(self):
        assert Ratios.getP_E(None, None, None, None, None) == None

    def test_getP_E(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getP_E(24, qtr1, qtr2, qtr3, qtr4) == 6

    def test_getP_E_Neg(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr1['diluted_eps_excluding_extraord_items'] = -5
        assert Ratios.getP_E(24, qtr1, qtr2, qtr3, qtr4) == None

    def test_getP_E_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr3 = None
        assert Ratios.getP_E(12, qtr1, qtr2, qtr3, qtr4) == 4


