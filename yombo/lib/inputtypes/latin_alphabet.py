import re

from yombo.lib.inputtypes.string import String


class Latin_Alphabet(String):

    def validate(self, value, **kwargs):
        value = super(Latin_Alphabet, self).validate(value, **kwargs)
        if re.match(r'[A-Za-z]{3,}', value):  # don't use isalnum, might be blank.
            return value

        raise AssertionError("Value is not within the latin alphabet.")