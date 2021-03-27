import unicodedata

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class UsernameValidator:
    message = (
        'Name is too short. You must have at least 3 letters in your name, '
        'or 2 letters and some digit(s).'
    )
    code = 'username_too_short'

    def __init__(self, message=None, code=None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def __call__(self, value):
        char_cats = [unicodedata.category(c)[0] for c in value]
        letters = char_cats.count('L')
        numerals = char_cats.count('N')
        if letters < 2 or letters + numerals < 3:
            raise ValidationError(self.message, code=self.code)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.message == other.message and
            self.code == other.code
        )
