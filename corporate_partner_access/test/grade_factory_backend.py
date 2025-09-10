
class CourseGradeFactoryMock:
    """Mock of CourseGradeFactory for testing purposes."""

    def read(self, user, course_key):
        """Mock read method."""
        return None
    

def course_grade_factory_class():
    """Return the mock CourseGradeFactory class."""
    return CourseGradeFactoryMock
