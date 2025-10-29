"""
These settings are here to use during tests, because django requires them.

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""

from os.path import abspath, dirname, join


def root(*args):
    """
    Get the absolute path of the given path relative to the project root.
    """
    return join(abspath(dirname(__file__)), *args)


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'default.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'flex_catalog',
    'partner_catalog',
    'organizations',
)

LOCALE_PATHS = [
    root('partner_catalog', 'conf', 'locale'),
]

ROOT_URLCONF = 'partner_catalog.urls'

SECRET_KEY = 'insecure-secret-key'

MIDDLEWARE = (
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': False,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',  # this is required for admin navigation sidebar
            'django.contrib.auth.context_processors.auth',  # this is required for admin
            'django.contrib.messages.context_processors.messages',  # this is required for admin
        ],
    },
}]

COURSE_OVERVIEW_BACKEND = "partner_catalog.test.course_overview_backend"
CERTIFICATES_MODULE_BACKEND = "partner_catalog.test.certificates_backend"
GRADE_FACTORY_MODULE_BACKEND = "partner_catalog.test.grade_factory_backend"
STUDENT_MODULE_BACKEND = "partner_catalog.test.student_module_backend"

# Celery settings for testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
