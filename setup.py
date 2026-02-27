from setuptools import find_packages, setup


setup(
    name='racetime',
    install_requires=[
        'asgiref>=3.5,<4.0',
        'beautifulsoup4>=4.11,<4.14',
        'channels[daphne]>=4.0,<5.0',
        'Django>=5.2,<6.1',
        'django-admin-list-filter-dropdown',
        'django-oauth-toolkit>=3.0,<4.0',
        'django-recaptcha>=4.0,<5.0',
        'hashids>=1.3,<1.4',
        'mpmath>=1.3,<1.4',
        'Pillow>=11.0,<12.0',
        'requests>=2.28,<3.0',
        'trueskill==0.4.5',
        'websockets>=15.0,<16.0',
    ],
    packages=find_packages(include=('racetime', 'racetime.*')),
)
