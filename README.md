<img src="https://uploads-ssl.webflow.com/6353a854c4fa2d460377c061/63642a6e9b19034a8b42547d_Group%2018-p-500.png" style="width: 200px;">
<br/>

## Supercharge your outbound with AI

<br/>
<br/>

<span><img src="https://shields.io/badge/coverage-84%25-yellow">
<img src="https://img.shields.io/badge/Flask-API-blue">
<img src="https://img.shields.io/badge/PostgreSQL-Database-blue">
<img src="https://img.shields.io/badge/Testing-212 unit tests-red"></span>

# Table of Contents

1. [SellScale API Overview](#sellscale-api-overview)
2. [Development](#development)
   1. [Overview](#overview)
   2. [Installation & Local Set Up](#installation--local-set-up)
   3. [Running Locally](#running-locally)
   4. [Making Changes](#making-changes)
   5. [Handling DB Migrations](#handling-db-migrations)
3. [Other](#other)
   1. [API Documentation](#api-documentation)
   2. [Helpful Bash Profiles](#bash-profiles)

# SellScale API Overview

SellScale API is a Flask app that stores data in a **PostgreSQL** database. We use **Redis** for storing items in a task queue and **Celery** to run tasks asynchronously. We also use several APIs like PhantomBuster, **OpenAI GPT-3**, iScraper, Clay API, Slack API, and more.

This API allows our staff and customers to do various things like:

- import prospects from CSVs
- generate & personalize outreach at scale
- automatically configure Phantom Busters
- fine tune NLP models
- run analytics jobs
- send notifications via Slack
  ... and more

# Development

## Overview

The source directory is as follows

```
- src
    - category 1
        - models.py
        - services.py
        - controllers.py
    - category 2
        - ...
    - ...
- testing
    - category 1
        - test_category1_models.py
        - test_category1_services.py
        - test_category1_controllers.py
    - category 2
        - ...
    - ...
```

This structure keeps our code clean and ensures we know where to find unit tests easily. We also have some general utils in the `utils` folder and `notebooks` for experiments in the notebooks folder.

## Installation & Local Set Up

If setting up from a fresh machine, make sure you have the following installed before continuing:

- Python3 <= 3.11 (For OSX `xcode-select --install`)
- Pip (For OSX `xcode-select --install`)
- [Postgres](https://www.postgresql.org/)
- [Brew](https://brew.sh/)

The following steps assume that you have the above prerequisites installed - any necessary installations should be added to the list above.

1.  Install `virtualenv` globally and use it to create your Python3 virtual environment. Make sure to run `virtualenv` in your working directory.

    ```
    pip install virtualenv
    virtualenv -p python3 venv
    ```

2.  Activate the virtual environment.

    ```
    source venv/bin/activate
    ```

3.  Install dependencies recursively from requirements file.

    ```
    pip install -r requirements.txt
    ```

4.  Download [Postgres App](https://postgresapp.com/) so you can create local & testing databases.

5.  In Postgres App, click any database - this should open a psql terminal window. Create two new databases through the terminal: `sellscale` for local testing, `testing` for unit testing (note that this db gets wiped between unit tests).

    ```
    create database sellscale;
    create database testing;
    ```

6.  Download [Postico 2](https://eggerapps.at/postico2/) - or your own PostgresSQL navigator of choice - to validate that the databases have been created (For Postico 2: New Server -> Fill in Database field with `sellscale` -> Connect. Repeat for `testing`).

7.  Create a `.local.env` file and paste the following example. Ensure that the `DATABASE_URL` points to your `sellscale` db.

    ```
    export FLASK_APP=app.py
    export FLASK_ENV='development'
    export APP_SETTINGS=config.DevelopmentConfig
    export ENCRYPTION_KEY='<YOUR_KEY_HERE>='
    export ISCRAPER_API_KEY='<YOUR_KEY_HERE>'
    export OPENAI_KEY='<YOUR_KEY_HERE>'
    export DATABASE_URL='postgresql://<YOUR_DEVICE>@localhost:5432/sellscale'
    export PHANTOMBUSTER_API_KEY='<YOUR_KEY_HERE>'
    export CELERY_REDIS_URL='redis://localhost:6379'
    export HUGGING_FACE_KEY='<YOUR_KEY_HERE>'
    ```

8.  Create a `.testing.env` file and paste the following example. Ensure that the `DATABASE_URL` points to your `testing` db.

    ```
    export FLASK_APP=app.py
    export FLASK_ENV='testing'
    export APP_SETTINGS=config.TestingConfig
    export ENCRYPTION_KEY='<YOUR_KEY_HERE>'
    export DATABASE_URL='postgresql://<YOUR_DEVICE>@localhost:5432/testing'
    export HUGGING_FACE_KEY='<YOUR_KEY_HERE>'
    ```

9.  Now you can upgrade your empty databases with the correct schemas. After running the following commands, use Postico to validate.

    ```
    source .local.env && flask db upgrade
    source .testing.env && flask db upgrade
    ```

10. Make sure that setup worked by running two tests.

- **Run Unit Tests**: Run all the unit tests by typing `source .testing.env && python -m pytest --cov=src -v`. There should not be any failures.

- **Boot Up Local API**: Run the API locally by typing `flask run`. You can then hit the endpoints using Postman.

## Running Locally

You may need to install Redis and Celery to run the API locally.

1. Make sure to `source .env`
2. In terminal #1, start Redis with `redis-server`
3. In terminal #2, start the Celery worker with `celery -A app.celery worker`
4. In terminal #3, start local SellScale API with `flask run`

## Making Changes

In general, when making changes, follow these guidelines:

1. Make a new branch:

```
<YOUR_NAME>_<YEAR-MONTH-DAY>_<DESCRIPTION-SEPARATED-BY-HYPHENS>
```

Examples would be `aakash_2023-01-01_adding-delete-api-for-prospects` or `david_2023-01-02_generate-new-hash-keys`

2. Check out the new branch, and make your feature changes. **INCLUDE DOC**

3. **Add unit tests!** (Do not forget to add unit tests!)

4. Run all unit tests locally. If everything passes, push to branch.

5. Get a peer review from a fellow engineer and have them 'check it off'

6. Verify your Pull Request in Github. If things look good, merge into Master (and it will automatically deploy via our Render pipeline)

🚨 **NOTE:** 🚨
This flow is different for Migrations. Migrations are very very _very_ risky so proceed with caution. Use the Migration guide later on in this README.

## Handling DB Migrations

At SellScale, our database runs on three technologies: PostgreSQL, SQLAlchemy, and Alembic.

- **PostgreSQL** - Our relational database of choice
- **SQLAlchemy** - An ORM layer over databases
- **Alembic** - our database versioning / migration tool of choice

We store data in a PostgreSQL database, interact with it via SQLAlchemy, and when we want to make changes to the underlying tables/databases, we use Alembic to make 'versioned changes'.

When make versioned changes, we need to be **very very careful** as we can permanently corrupt data and/or delete data!

Best to do this in pairs until you are certain you know what you are doing.

Steps:

1. Make an update to the model in the relevant `models.py` file.

2. Create a migration file by running `flask db migrate`.

3. This will create a new file with a hash (linked in terminal). Open the file and edit the first line to describe the change. This documents what changes are being made to the schema.

4. Set yourself to a local environment by running `source .env` and then run `flask db upgrade`. If everything works, check a couple endpoints and ensure server is running.

5. Now switch to the testing environment by running `source .envtesting` and then run `flask db upgrade`. Run all unit tests and make sure things are passing!

6. Create a branch, and push your changes like usual. **ABSOLUTELY** get a peer review on DB Migrations before merging.

7. SSH into a staging pod using Render. In the staging pod, run `flask db upgrade` and ensure Staging API works as expected.

8. If staging works, run it on production by SSH-ing into a production pod and running `flask db upgrade`.

Verify everything works! Do this with a pair to be cautious.

Do not run migrations late at night or on Friday nights when you want to go home - usually ends in demise.

# Other

## API Documentation

**Please, please use PyDoc to document your code.** It makes it easier for others to understand your code.

The following is a helpful VSCode extension for generating PyDoc comments: [autoDocstring](https://marketplace.visualstudio.com/items?itemName=njpwerner.autodocstring)

## Precommit Hooks

We use [pre-commit](https://pre-commit.com/) to run a series of checks before committing code.

Python specific:

- **Black** - auto-formatter for Python
- **Flake8** - linter for Python
- **PyLint** - linter for Python
- **Bandit** - security linter for Python
- **pydocstyle** - linter for Python docstrings
- **isort** - auto-import sorter for Python
- **autoflake** - auto-import remover for Python

Generic:

- **trailing-whitespace** - removes trailing whitespace
- **end-of-file-fixer** - ensures files end with a newline
- **check-yaml** - checks YAML files for syntax errors
- **check-added-large-files** - checks for large files added to the repo
- **double-quote-string-fixer** - ensures strings are double-quoted
- **name-tests-test** - ensures test files are named correctly
- **requirements-txt-fixer** - ensures requirements.txt is sorted
- **debug-statements** - ensures debug statements are removed

## Helpful Bash Profiles

Here are some shortcuts that we find really useful to get the local and testing environment up and running quickly. Feel free to copy/paste into your local `.bash_profile` or `.bashrc` file or `.zshrc` file.

```bash
# Opens VSCode project quickly
alias ssapi='code /Users/YOUR_USER/YOUR_PATH/sellscale-api'
alias sssight='code /Users/YOUR_USER/YOUR_PATH/sellscale-sight'

# The following need to be from SellScale directory
alias prod='source .envprod'
alias staging='source .envstaging'
alias dev='source .env'

alias server='flask run'
alias celery='celery -A app.celery worker'
alias redis='redis-server'
```
