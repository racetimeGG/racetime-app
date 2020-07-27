from setuptools import setup


setup(
    name='racetime',
    install_requires=[
        'asgiref>=3.2.3',
        'beautifulsoup4>=4.8.2,<4.10',
        'channels>=2.4.0,<2.5',
        'Django>=3.0.1,<3.1',
        'django-admin-list-filter-dropdown',
        'django-oauth-toolkit>=1.2.0,<1.4',
        'django-recaptcha>=2.0.5,<2.1',
        'hashids>=1.2.0,<1.3',
        'Pillow>=6.2.1,<7.3',
        'requests>=2.22.0,<2.25',
        'trueskill==0.4.5',
    ],
)
