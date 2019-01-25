import string
import re
import random
import datetime


class AString(str):
    """AString represents "Aries String", a sub-class of python built-in str with additional methods.
    AString inherits all methods of the python str.
    Instance of AString can be use in place of python str.

    For methods in python str returning a str, list, or tuple,
        additional post-processing are added to convert the returning str values to instances AString.
        e.g., AString("hello").title() will return AString("Hello").
    This is designed to enable method chaining for AString methods,
        e.g., AString("hello").title().append_today().

    """
    def __new__(cls, string_literal):
        return super(AString, cls).__new__(cls, string_literal)

    def __getattribute__(self, item):
        """Wraps the existing methods of python str to return AString objects instead of build-in strings.
        If the existing method returns a str, it will be converted to an instance of AString.
        If the existing method returns a list or tuple,
            the str values in the list or tuple will be converted to instances of AString.

        See Also:
            https://docs.python.org/3.5/reference/datamodel.html#object.__getattribute__
            https://stackoverflow.com/questions/7255655/how-to-subclass-str-in-python

        """
        if item in dir(str):  # only handle str methods here
            def method(s, *args, **kwargs):
                value = getattr(super(AString, self), item)(*args, **kwargs)
                # Return value is str, list, tuple:
                if isinstance(value, str):
                    return type(s)(value)
                elif isinstance(value, list):
                    return [type(s)(i) for i in value]
                elif isinstance(value, tuple):
                    return tuple(type(s)(i) for i in value)
                else:
                    # dict, bool, or int
                    return value
            # Bound method
            return method.__get__(self, type(self))
        else:
            # Delegate to parent
            return super(AString, self).__getattribute__(item)

    def prepend(self, s, delimiter='_'):
        """Prepends the string with another string or a list of strings, connected by the delimiter.

        Args:
            s (str/list): A string or a list of strings to be prepended to the filename.
            delimiter: A string concatenating the original filename and each of the prepended strings.

        Returns: An AString instance

        """
        if not isinstance(s, list):
            s = [s]
        return AString(delimiter.join(s + [self]))

    def append(self, s, delimiter='_'):
        """Appends a list of strings, connected by the delimiter.

        Args:
            s (str/list): A string or a list of strings to be appended to the filename.
            delimiter: A string concatenating the original filename and each of the appended strings.

        Returns: An AString instance

        """
        if not isinstance(s, list):
            s = [s]
        return AString(delimiter.join([self] + s))

    def append_datetime(self, dt=datetime.datetime.now(), fmt="%Y%m%d_%H%M%S"):
        """Appends date and time.
        The current date and time will be appended by default.

        Args:
            dt (datetime.datetime): A datetime.datetime instance.
            fmt (str): The format of the datetime.

        Returns: An AString instance

        """
        datetime_string = dt.strftime(fmt)
        return self.append(datetime_string)

    def append_today(self, fmt="%Y%m%d"):
        """Appends today's date.

        Args:
            fmt (str): The format of the date.

        Returns: An AString instance

        """
        return self.append_datetime(fmt=fmt)

    def append_random(self, choices, n):
        """Appends a random string of n characters.

        Args:
            choices (str): A string including the choices of characters.
            n (int): The number of characters to be appended.

        Returns: An AString instance

        """
        random_chars = ''.join(random.choice(choices) for _ in range(n))
        return self.append(random_chars)

    def append_random_letters(self, n):
        """Appends a random string of letters.

        Args:
            n (int): The number of characters to be appended.

        Returns: An AString instance

        """
        return self.append_random(string.ascii_letters, n)

    def append_random_uppercase(self, n):
        """Appends a random string of uppercase letters.

        Args:
            n (int): The number of characters to be appended.

        Returns: An AString instance

        """
        return self.append_random(string.ascii_uppercase, n)

    def append_random_lowercase(self, n):
        """Appends a random string of lowercase letters.

        Args:
            n (int): The number of characters to be appended.

        Returns: An AString instance

        """
        return self.append_random(string.ascii_lowercase, n)

    def remove_non_alphanumeric(self):
        """Removes non alpha-numeric characters from a string, including space and special characters.

        Returns: An AString with only alpha-numeric characters.

        """
        new_str = "".join([
            c for c in self
            if (c in string.digits or c in string.ascii_letters)
        ])
        return AString(new_str)

    def remove_escape_sequence(self):
        """Removes ANSI escape sequences, including color codes.

        Returns: An AString with escape sequence removed.

        """
        return AString(re.sub(r"\x1b\[.*m", "", self))


class FileName(AString):
    """Represents a filename and provides methods for modifying the filename.

    A "filename" is a string consist of a "basename" and an "extension".
    For example, in filename "hello_world.txt", "hello_world" is the basename and ".txt" is the extension.
    The extension can also be empty string. The filename will not contain a "." if the extension is empty.
    For example, "hello_world" is a filename with no extension.

    This class provides methods for modifying the "basename" of the filename.
    No modification will be applied to the "extension".

    This class is a sub-class of AString
    Most methods in this class support "Method Chaining", i.e. they return the FileName instance itself.

    Warnings:
        All methods will be operate on the "basename".
        Especially, len() will only return the length of the basename.

    """
    def __new__(cls, string_literal):
        name_splits = string_literal.rsplit('.', 1)
        a_string = super(FileName, cls).__new__(cls, name_splits[0])
        a_string.basename = name_splits[0]
        if len(name_splits) == 1:
            a_string.extension = ""
        else:
            a_string.extension = name_splits[1]
        return a_string

    def __getattribute__(self, item):
        """Wraps the existing methods of python AString to return FileName objects.
        """
        if item in dir(AString):
            def method(s, *args, **kwargs):
                value = getattr(super(FileName, self), item)(*args, **kwargs)
                if isinstance(value, AString) or isinstance(value, str):
                    filename = type(s)("%s" % value)
                    filename.extension = self.extension
                    return filename
                else:
                    return value
            # Bound method
            return method.__get__(self, type(self))
        else:
            # Delegate to parent
            return super(FileName, self).__getattribute__(item)

    def __str__(self):
        """Convert the FileName object to a string including basename and extension.
        """
        if self.extension:
            return "%s.%s" % (self.basename, self.extension)
        else:
            return self.basename

    @property
    def name_without_extension(self):
        """The filename without extension.
        """
        return self.basename

    def to_string(self):
        """Convert the FileName object to a string including basename and extension.
        """
        return str(self)

