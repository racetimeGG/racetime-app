from setuptools import find_packages, setup


setup(
    name='racetime',
    install_requires=[
        'asgiref>=3.5,<3.6',
        'beautifulsoup4>=4.11,<4.12',
        'channels>=3.0,<4.0',
        'Django>=3.2,<3.3',
        'django-admin-list-filter-dropdown',
        'django-oauth-toolkit>=1.7,<2.0',
        'django-recaptcha>=3.0,<3.1',
        'hashids>=1.3,<1.4',
        'mpmath>=1.2,<1.3',
        'Pillow>=9.3,<10.0',
        'requests>=2.28,<2.29',
        'trueskill==0.4.5',
        'websockets>=10.4,<11.0',
    ],
    packages=find_packages(include=('racetime', 'racetime.*')),
)
