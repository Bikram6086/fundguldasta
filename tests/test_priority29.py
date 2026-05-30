"""
Priority 29 tests — Index Bouquet engine and API endpoint.
Run: pytest tests/test_priority29.py -v
"""
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from engine.index_bouquet import get_index_bouquets, BOUQUET_DEFS, INDEX_FUNDS


class TestIndexBouquetEngine:

    def test_returns_five_bouquets(self):
        bs = get_index_bouquets()
        assert len(bs) == 5

    def test_one_simple_four_detailed(self):
        bs = get_index_bouquets()
        assert sum(1 for b in bs if b['type'] == 'simple') == 1
        assert sum(1 for b in bs if b['type'] == 'detailed') == 4

    def test_allocations_sum_to_100(self):
        bs = get_index_bouquets()
        for b in bs:
            total = sum(f['weight'] for f in b['funds'])
            assert total == 100, f"{b['id']} weights sum to {total}"

    def test_weighted_ter_positive(self):
        bs = get_index_bouquets()
        for b in bs:
            assert b['weighted_ter'] > 0, f"{b['id']} has zero TER"
            assert b['weighted_ter'] < 1.0, f"{b['id']} TER unreasonably high"

    def test_nav_data_present_for_all_slots(self):
        bs = get_index_bouquets()
        for b in bs:
            for f in b['funds']:
                assert f['nav_count'] > 200, f"{f['short_name']} has only {f['nav_count']} NAVs"

    def test_cagr_reasonable(self):
        bs = get_index_bouquets()
        for b in bs:
            for f in b['funds']:
                if f['cagr_3y'] is not None:
                    assert -50 < f['cagr_3y'] < 100, f"{f['short_name']} 3yr CAGR {f['cagr_3y']} out of range"
                if f['cagr_5y'] is not None:
                    assert -30 < f['cagr_5y'] < 80, f"{f['short_name']} 5yr CAGR {f['cagr_5y']} out of range"

    def test_simple_bouquet_has_two_funds(self):
        bs = get_index_bouquets()
        simple = next(b for b in bs if b['type'] == 'simple')
        assert len(simple['funds']) == 2

    def test_scheme_codes_in_index_funds(self):
        codes = {f['scheme_code'] for f in INDEX_FUNDS.values()}
        assert '120716' in codes  # UTI Nifty 50
        assert '145552' in codes  # Motilal Nasdaq 100
        assert '148726' in codes  # Nippon Midcap 150
        assert '148519' in codes  # Nippon Smallcap 250

    def test_bouquet_ids_unique(self):
        bs = get_index_bouquets()
        ids = [b['id'] for b in bs]
        assert len(ids) == len(set(ids))

    def test_horizon_ordering(self):
        bs = get_index_bouquets()
        detailed = [b for b in bs if b['type'] == 'detailed']
        mins = [b['horizon_min'] for b in detailed]
        assert mins == sorted(mins), "Detailed bouquets should be ordered by horizon_min"
