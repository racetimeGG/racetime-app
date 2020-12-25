# racetime.gg

[![Discord](https://discordapp.com/api/guilds/660452709044060171/embed.png?style=shield)](https://discord.racetime.gg)
[![Twitter Follow](https://img.shields.io/twitter/follow/racetimeGG?style=social)](https://twitter.com/racetimeGG)

This is the main code repository for [racetime.gg](https://racetime.gg), a
website for organising races online, with a focus on video games and speedruns.

## Quick setup guide

If you're ready to start hacking the code, read on.

The recommended way to run a development environment is using
[Docker](https://www.docker.com/). You can download install Docker Desktop
for your machine, which will allow you to spin up a full copy of the site in
isolation, with all its dependencies fulfilled.

Make sure that Docker has the ability to share the repository directory with
containers. On Docker Desktop, look for "Shared Drives" or "File Sharing" under
settings to configure this.

### Setup instructions

1. Clone this repository.
1. Copy `project/settings/local.py.example` to `project/settings/local.py`.
1. Edit the local.py file above and set your
   [dev.twitch.tv](https://dev.twitch.tv) client credentials.
1. Run `npm install` to grab JS dependencies (you'll need
   [NodeJS](https://nodejs.org/en/) installed).
1. Start the environment with `docker-compose up --build -d`.
1. Run `docker-compose exec racetime.web python manage.py migrate` to set up a
   database with migrations.
   * Note: you may need to wait a minute or two for the environment to be ready.
1. (Optional) Run
   `docker-compose exec racetime.web python manage.py createsuperuser` to
   create a superuser account that you can log in as.
1. (Optional) Run
   `docker-compose exec racetime.web python manage.py creatersakey` to
   generate an RSA key to be used by the racetime API and OpenID Connect provider.
1. (Optional) Run
   `docker-compose exec racetime.web python manage.py fixtures` to set up some
   basic data for testing purproses (e.g. users and race categories).
   * Users created by the fixtures command will have password `pass`.

The site will now be available to browse on
[http://localhost:8000](http://localhost:8000), so take a look around!

You can watch the logs of all containers by running `docker-compose logs -f`,
or by running `docker-compose up` without the `-d` (detatch) flag. Beware that
if you do the latter then Ctrl+C will kill off the containers and stop your
environment, so it's probably better to use something like
`docker-compose up -d && docker-compose logs -f`.

### Notes and caveats

#### Binding a different port number

The `docker-compose.yml` file attaches the web container to port 8000 by
default. If you need to override this, create a `docker-compose.override.yml`
file with the following contents:

```yaml
version: '3.6'

services:
  racetime.web:
    ports:
      - "<LOCAL>:8000"
```

Replace `<LOCAL>` with whatever port number you'd like.

#### Expose the database port

If you'd like to use a fancy client app to browse the database, you can set up
a `docker-compose.override.yml` file to expose the database port to your local
machine:

```yaml
version: '3.6'

services:
  racetime.db:
    ports:
      - "<LOCAL>:3306"
```

Replace `<LOCAL>` with whatever port number you'd like. The DB username,
password and database name are all `racetime` by default.

#### localhost vs. 127.0.0.1

You should not use an IP address to connect to the website in your browser, as
this is not compatible with the Twitch API. Always use
[http://localhost:8000](http://localhost:8000) to access the server instead of
`http://127.0.0.1:8000`.

#### Windows

If you're developing on Windows, make sure to check out this repository with
Linux-style line endings (LF not CRLF), in particular you need to make sure the
Bash scripts in the `.docker` directory have the correct line endings or they
will fail to execute.

## Further information

The [Wiki](https://github.com/racetimeGG/racetime-app/wiki) pages have some
information that may prove useful to you. We also have a Discord server where
you can discuss the site and ongoing developments, make suggestions and get
involved: [join the Discord server here](https://discord.racetime.gg).

## Contributing

All contributions are welcome to help improve the site. Whether you're good at
coding, or designing, or simply want to spread the word, you can help us make
racing and speedruns better for everyone. Join up to the Discord server if you
want to get more involved!
