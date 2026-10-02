"""This file contains all the necessary backends in a test scenario for courseware."""


class ItemNotFoundErrorMock(Exception):
    """Stand-in for xmodule.modulestore.exceptions.ItemNotFoundError."""


def get_course_blocks_completion_summary(course_key, user):  # pylint: disable=unused-argument
    """Fake completion summary: no progress recorded."""
    return None


def item_not_found_error():
    """Return the fake ItemNotFoundError exception class."""
    return ItemNotFoundErrorMock
