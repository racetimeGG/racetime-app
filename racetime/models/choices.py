class Choice:
    """
    Base choice set. This sets up some syntactic sugar to make it a bit easier
    to handle raw values, labels and helpful descriptions as a grouping.
    """
    def __init__(self, value, verbose_value, help_text=None):
        self.value = value
        self.verbose_value = verbose_value
        self.help_text = help_text

    def __eq__(self, other):
        if isinstance(other, Choice):
            return self == other
        return str(self) == other

    def __str__(self):
        return self.value

    def __hash__(self):
        return hash(self.value)


class ChoiceSet(type):
    """
    Metaclass for the choice set, used to make it easier to get all choices at
    once.
    """
    @property
    def choices(cls):
        return tuple((choice.value, choice.verbose_value) for choice in cls.all)

    def __getattr__(self, item):
        try:
            return next(filter(lambda choice: str(choice) == item, self.all))
        except StopIteration:
            raise AttributeError


class EntrantStates(metaclass=ChoiceSet):
    """
    Possible states for a race entrant.
    """
    all = (
        Choice('requested', 'Requesting to join', 'User wishes to enter the race'),
        Choice('invited', 'Invited to join', 'User has been invited to join this race'),
        Choice('declined', 'Declined invitation', 'User has refused their invitation'),
        Choice('joined', 'Joined', 'User has entered the race'),
        Choice('partitioned', 'Partitioned', 'User has been partitioned into a separate race'),
    )


class RaceStates(metaclass=ChoiceSet):
    """
    Possible states for a race.
    """
    all = (
        Choice('open', 'Open', 'Anyone may join this race'),
        Choice('invitational', 'Invitational', 'Only invitees may join this race'),
        Choice('pending', 'Getting ready', 'Waiting for race to begin'),
        Choice('in_progress', 'In progress', 'Race is in progress'),
        Choice('finished', 'Finished', 'This race has been completed'),
        Choice('cancelled', 'Cancelled', 'This race has been cancelled'),
        Choice('partitioned', 'Partitioned', 'Race has been partitioned into separate 1v1 races'),
    )
    current = all[:4]
    past = all[4:]
