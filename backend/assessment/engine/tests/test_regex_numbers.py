import pytest

from assessment.engine import regex_numbers as rn


class TestExtractHours:
    def test_range_hours_averages(self):
        assert rn.extract_hours("I sleep about 7-8 hours a night") == 7.5

    def test_single_hours(self):
        assert rn.extract_hours("I get 6 hours of sleep") == 6.0

    def test_to_range(self):
        assert rn.extract_hours("around 5 to 6 hours") == 5.5

    def test_no_match(self):
        assert rn.extract_hours("I feel tired") is None


class TestExtractLitres:
    def test_litres_direct(self):
        assert rn.extract_litres("I drink 2 litres of water") == 2.0

    def test_ml(self):
        assert rn.extract_litres("about 500 ml a day") == 0.5

    def test_glasses_range(self):
        assert rn.extract_litres("maybe 4-5 glasses a day") == pytest.approx(1.125)

    def test_glasses_single(self):
        assert rn.extract_litres("2 glasses of water") == 0.5

    def test_no_match(self):
        assert rn.extract_litres("I don't drink much") is None


class TestExtractDaysPerWeek:
    def test_twice_a_week(self):
        assert rn.extract_days_per_week("I exercise twice a week") == 2

    def test_numeric_times_a_week(self):
        assert rn.extract_days_per_week("I go running 3 times a week") == 3

    def test_daily(self):
        assert rn.extract_days_per_week("I walk every day") == 7

    def test_never(self):
        assert rn.extract_days_per_week("I don't exercise at all") == 0

    def test_no_match(self):
        assert rn.extract_days_per_week("I feel fine") is None


class TestExtractMinutes:
    def test_minutes_direct(self):
        assert rn.extract_minutes("about 30 minutes each time") == 30

    def test_half_hour(self):
        assert rn.extract_minutes("half an hour of walking") == 30

    def test_hour_session(self):
        assert rn.extract_minutes("a 1 hour exercise session") == 60

    def test_no_match(self):
        assert rn.extract_minutes("I feel tired") is None


class TestExtractCigarettesPerDay:
    def test_direct(self):
        assert rn.extract_cigarettes_per_day("about 10 cigarettes a day") == 10

    def test_pack(self):
        assert rn.extract_cigarettes_per_day("I smoke a pack a day") == 20

    def test_half_pack(self):
        assert rn.extract_cigarettes_per_day("half a pack a day") == 10

    def test_none(self):
        assert rn.extract_cigarettes_per_day("I don't smoke") is None
