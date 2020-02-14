from django.apps import apps
from django.db.transaction import atomic
from trueskill import Rating, global_env


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

    def save(self):
        self.ranking.save()

    def set_rating(self, rating, finish_time):
        score_change = rating.mu - self.rating.mu

        if finish_time and (
            not self.ranking.best_time
            or finish_time < self.ranking.best_time
        ):
            self.ranking.best_time = finish_time
        self.ranking.score = rating.mu
        self.ranking.confidence = rating.sigma
        self.ranking.save()

        self.entrant.score_change = score_change
        self.entrant.save()

        self.rating = rating


def rate_race(race):
    env = global_env()
    entrants = race.ordered_entrants
    users = [
        UserRating(entrant, race)
        for entrant in entrants
    ]
    rating_groups = [(user.rating,) for user in users]
    num_finished = len([entrant for entrant in entrants if entrant.place])
    ranks = [
        entrant.place if entrant.place else num_finished + 1
        for entrant in entrants
    ]
    rated = env.rate(rating_groups, ranks)

    with atomic():
        for group, user_rating, entrant in zip(rated, users, entrants):
            rating = group[0]
            user_rating.set_rating(rating, entrant.finish_time)
