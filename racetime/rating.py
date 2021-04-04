from collections import defaultdict
from datetime import timedelta

from django.apps import apps
from django.db.transaction import atomic
from trueskill import Rating, TrueSkill


class UserRating:
    def __init__(self, entrant, race):
        UserRanking = apps.get_model('racetime', 'UserRanking')

        self.entrant = entrant
        self.user = entrant.user
        try:
            self.ranking = UserRanking.objects.get(
                user=entrant.user,
                category=race.category,
                goal=race.goal,
            )
            self.rating = Rating(mu=self.ranking.score, sigma=self.ranking.confidence)
        except UserRanking.DoesNotExist:
            self.rating = Rating()
            self.ranking = UserRanking(
                user=entrant.user,
                category=race.category,
                goal=race.goal,
                score=self.rating.mu,
                confidence=self.rating.sigma,
            )
            self.ranking.rating = self.ranking.calculated_rating

    def save(self):
        self.ranking.save()

    def set_rating(self, rating):
        original_rating = self.ranking.rating

        if self.entrant.finish_time and (
            not self.ranking.best_time
            or self.entrant.finish_time < self.ranking.best_time
        ):
            self.ranking.best_time = self.entrant.finish_time
        self.ranking.score = rating.mu
        self.ranking.confidence = rating.sigma
        self.ranking.rating = self.ranking.calculated_rating
        self.ranking.times_raced += 1
        self.ranking.save()

        self.entrant.rating_change = self.ranking.calculated_rating - original_rating
        self.entrant.save()

        self.rating = rating


def _sort_key(group):
    entrants = [user.entrant for user in group]
    if any(entrant.dnf or entrant.dq for entrant in entrants):
        return timedelta.max
    finish_times = [entrant.finish_time for entrant in entrants]
    return sum(finish_times, timedelta(0)) / len(finish_times)


def rate_race(race):
    entrants = race.ordered_entrants
    users = [
        UserRating(entrant, race)
        for entrant in entrants
    ]
    if not race.team_race:
        groups = [(user,) for user in users]
    else:
        groups = defaultdict(list)
        for user in users:
            groups[user.entrant.team_id].append(user)
        groups = list(groups.values())
        groups.sort(key=_sort_key)

    rating_groups = []
    ranks = []
    current_rank = 0
    for group in groups:
        sort_key = _sort_key(group)
        rating_groups.append(tuple(user.rating for user in group))
        ranks.append(current_rank)
        if sort_key < timedelta.max:
            current_rank += 1

    env = TrueSkill(backend='mpmath')
    rated = env.rate(rating_groups, ranks)

    with atomic():
        for ratings, group in zip(rated, groups):
            for rating, user in zip(ratings, group):
                user.set_rating(rating)
