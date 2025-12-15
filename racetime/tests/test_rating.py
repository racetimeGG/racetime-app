from datetime import timedelta
from types import SimpleNamespace
from django.test import SimpleTestCase

from racetime.rating import build_rating_groups_by_rank

class FakeUser:
    def __init__(self, rating, finish_time, dnf=False, dq=False):
        self.rating = rating
        self.entrant = SimpleNamespace(
            finish_time=finish_time,
            dnf=dnf,
            dq=dq,
        )

class BuildRatingGroupsByRankTests(SimpleTestCase):

    def test_build_rating_groups_by_rank_simple_order(self):
        user1 = FakeUser(1, timedelta(minutes=10))
        user2 = FakeUser(2, timedelta(minutes=20))
        user3 = FakeUser(3, timedelta(minutes=30))
        user_tie_1 = FakeUser(4, timedelta(minutes=40)) # Tie. Current design is to assign different ranks.
        user_tie_2 = FakeUser(5, timedelta(minutes=40)) # Tie. Current design is to assign different ranks.
        user_dnf_1 = FakeUser(6, timedelta.max)  # DNF
        user_dnf_2 = FakeUser(7, timedelta.max)  # DNF

        groups = [
            [user1],
            [user2],
            [user3],
            [user_tie_1],
            [user_tie_2],
            [user_dnf_1],
            [user_dnf_2],
        ]

        rating_groups, ranks = build_rating_groups_by_rank(groups)

        assert ranks == [0, 1, 2, 3, 4, 5, 5]
        assert rating_groups == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]
