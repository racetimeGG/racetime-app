from setuptools import setup


setup(
    name='racetime',
    install_requires=[
        'beautifulsoup4>=4.8.2,<4.9',
        'Django>=3.0.1,<3.1',
        'django-recaptcha>=2.0.5,<2.1',
        'hashids>=1.2.0,<1.3',
        'Pillow>=6.2.1,<6.3',
        'requests>=2.22.0,<2.23',
        'trueskill==0.4.5',
    ],
)
