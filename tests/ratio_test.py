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
        neg_qtr1 = dict(qtr1)
        neg_qtr1['diluted_eps_excluding_extraord_items'] = -5
        assert Ratios.getP_E(24, neg_qtr1, qtr2, qtr3, qtr4) == None

    def test_getP_E_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr3 = None
        assert Ratios.getP_E(12, qtr1, qtr2, qtr3, qtr4) == 4


class Test_GetEV_EBITDA(object):
    @pytest.fixture
    def setup(self):
        qtr1 = {'operating_income': 5,
                'depreciation/amortization': 3,
                'depreciation/depletion': 2,
                'amortization': 1}
        qtr2 = qtr1
        qtr3 = qtr1
        qtr4 = qtr1
        return qtr1, qtr2, qtr3, qtr4

    def test_getEV_EBITDA_None(self):
        assert Ratios.getEV_EBITDA(None, None, None, None, None) == None

    def test_getEV_EBITDA(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getEV_EBITDA(100, qtr1, qtr2, qtr3, qtr4) == 3.125

    def test_getEV_EBITDA_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr1_mod = dict(qtr1)
        qtr2_mod = dict(qtr2)
        del qtr1_mod['depreciation/amortization']
        del qtr2_mod['depreciation/amortization']
        del qtr2_mod['depreciation/depletion']
        assert round(Ratios.getEV_EBITDA(100, qtr1_mod, qtr2_mod, qtr3, qtr4), 3) == 3.448

    def test_getEV_EBITDA_Neg(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr1_mod = dict(qtr1)
        qtr1_mod['operating_income'] = -30
        assert Ratios.getEV_EBITDA(100, qtr1_mod, qtr2, qtr3, qtr4) == None

    def test_getEV_EBITDA_MixedNone(self, setup):
        qtr1, qtr2 = setup[0:2]
        assert Ratios.getEV_EBITDA(100, qtr1, qtr2, None, None) == 6.25


class Test_GetP_B(object):
    @pytest.fixture
    def setup(self):
        data = {'total_equity': 300,
                'total_common_shares_outstanding': 100,
                'redeemable_preferred_stock': 30,
                'preferred_stock_non_redeemable': 20}
        return data

    def test_getP_B_None(self):
        assert Ratios.getP_B(10, None) == None

    def test_getP_B(self, setup):
        data = setup
        assert Ratios.getP_B(10, data) == 4

    def test_getP_B_Neg(self, setup):
        data = setup
        data['total_equity'] = -120
        assert Ratios.getP_B(10, data) == None

    def test_getP_B_Mixed(self, setup):
        data = setup
        del data['redeemable_preferred_stock']
        del data['preferred_stock_non_redeemable']
        data['total_equity'] = 500
        assert Ratios.getP_B(10, data) == 2


class Test_GetEV_S(object):
    @pytest.fixture
    def setup(self):
        qtr1 = {'total_revenue': 500}
        qtr2 = qtr1
        qtr3 = qtr1
        qtr4 = qtr1
        return qtr1, qtr2, qtr3, qtr4

    def test_getEV_S_None(self):
        assert Ratios.getEV_S(None, None, None, None, None) == None

    def test_getEV_S(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getEV_S(100, qtr1, qtr2, qtr3, qtr4) == 0.05

    def test_getEV_S_Neg(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        neg_qtr1 = dict(qtr1)
        neg_qtr1['total_revenue'] = -1600
        assert Ratios.getEV_S(100, neg_qtr1, qtr2, qtr3, qtr4) == None

    def test_getEV_S_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr3 = None
        qtr2 = None
        assert Ratios.getEV_S(100, qtr1, qtr2, qtr3, qtr4) == 0.1


class Test_GetEV_FCF(object):
    @pytest.fixture
    def setup(self):
        qtr1 = {'cash_from_operating_activities': 50,
                'capital_expenditures': -20}
        qtr2 = qtr1
        qtr3 = qtr1
        qtr4 = qtr1
        return qtr1, qtr2, qtr3, qtr4

    def test_getEV_FCF_None(self):
        assert Ratios.getEV_FCF(None, None, None, None, None) == None

    def test_getEV_FCF(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getEV_FCF(600, qtr1, qtr2, qtr3, qtr4) == 5

    def test_getEV_FCF_Neg(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        neg_qtr1 = dict(qtr1)
        neg_qtr1['cash_from_operating_activities'] = -200
        assert Ratios.getEV_FCF(600, neg_qtr1, qtr2, qtr3, qtr4) == None

    def test_getEV_FCF_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr3 = None
        qtr2 = None
        assert Ratios.getEV_FCF(600, qtr1, qtr2, qtr3, qtr4) == 10


class Test_GetDivPayout(object):
    @pytest.fixture
    def setup(self):
        qtr1 = {'dps_common_stock_primary_issue': .24}
        qtr2 = qtr1
        qtr3 = qtr1
        qtr4 = qtr1
        return qtr1, qtr2, qtr3, qtr4

    def test_getDivPayout_None(self):
        assert Ratios.getDivPayout(None, None, None, None) == 0

    def test_getDivPayout(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getDivPayout(qtr1, qtr2) == .48

    def test_getDivPayout_Year(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        assert Ratios.getDivPayout(qtr1, qtr2, qtr3, qtr4) == .96

    def test_getDivPayout_Mixed(self, setup):
        qtr1, qtr2, qtr3, qtr4 = setup
        qtr1 = None
        qtr3 = None
        assert Ratios.getDivPayout(qtr1, qtr2, qtr3, qtr4) == .48
