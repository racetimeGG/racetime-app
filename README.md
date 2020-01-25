# racetime.gg

[![Discord](https://discordapp.com/api/guilds/660452709044060171/embed.png?style=shield)](https://discord.gg/65cvHG3)

This is the main code repository for [racetime.gg](https://racetime.gg), a
website for organising races online, with a focus on video games and speedruns.

## Quick setup guide

Follow these instructions to get a development environment up and running.

1. Install [Python](https://www.python.org/) (minimum 3.7) and
   [NodeJS](https://nodejs.org/en/) (minimum 12.14.0 recommended).
1. Clone this repository.
1. Copy `project/settings/local.py.example` to `project/settings/local.py`
1. Edit the local.py file above and set your Twitch.tv client credentials.
1. From the repo's base directory, run `pip install -e .` to install Python
   dependencies. You can use a virtualenv for this, if you like.
1. Again from the base directory, run `npm install` to install JavaScript
   libraries.
1. Run `python manage.py migrate` to set up a database file with migrations.
1. (Optional) Run `python manage.py createsuperuser` to create a superuser
   account that you can log in as.
1. (Optional) Run `python manage.py fixtures` to set up some basic data for
   testing purproses (e.g. users and race categories).
   * Users created by the fixtures command will have password `pass`.

Now you should be ready to run a development environment by running these two
commands in parallel:

```
python manage.py runserver
python manage.py racebot
```

The first command will set up Django's development webserver, which by default
runs on [http://localhost:8000](http://localhost:8000). If this fails, look at
the Django docs for help.

The second command runs an instance of the race bot, which will observe ongoing
races and perform any time-sensitive operations needed on them.

### Notes and caveats

#### Multiple Python versions

If you have multiple Python versions installed or you have not added Python to
your PATH, some of the commands above may need adjusting, e.g. by using
`python3` and `pip3` in place of `python`/`pip`. Double-check what you have
installed if you have any issues creating the environment.

#### localhost vs. 127.0.0.1

Although django suggests using the IPv4 address when accessing the web server,
this is not compatible with the Twitch API, so you should always use
[http://localhost:8000](http://localhost:8000) to access the server instead of
`http://127.0.0.1:8000`.

## Further information

The [Wiki](/wiki) pages have some information that may prove useful to you.
We also have a Discord server where you can discuss the site and ongoing
developments, make suggestions and get involved:
[join the Discord server here](https://discord.gg/65cvHG3).

## Contributing

All contributions are welcome to help improve the site. Whether you're good at
coding, or designing, or simply want to spread the word, you can help us make
racing and speedruns better for everyone. Join up to the Discord server if you
want to get more involved!
