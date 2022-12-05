<img src="https://uploads-ssl.webflow.com/6353a854c4fa2d460377c061/63642a6e9b19034a8b42547d_Group%2018-p-500.png" style="width: 200px;">
<br/>
Supercharge your outbound with AI

<br/>
<br/>

<span><img src="https://shields.io/badge/coverage-75%25-yellow">
<img src="https://img.shields.io/badge/Flask-API-blue">
<img src="https://img.shields.io/badge/PostgreSQL-Database-blue">
<img src="https://img.shields.io/badge/Testing-87 unit tests-red"></span>

## SellScale API Overview

SellScale API is a Flask app that stores data in a PostgreSQL database. We use Redis for storing items in a task queue and Celery to run tasks asynchronously. We also use several APIs like PhantomBuster, OpenAI GPT-3, iScraper, Clay API, Slack API, and more.

This API allows our staff and customers to do various things like:

- import prospects from CSVs
- generate & personalize outreach at scale
- automatically configure Phantom Busters
- fine tune NLP models
- run analytics jobs
- send notifications via Slack
  ... and more

Main folders are as follows

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

## To Run API Locally

1. Open three terminals and `source .env`. Get source file from a fellow engineer.
2. In terminal #1, start Redis with `redis-server`
3. In terminal #2, start the Celery worker with `celery -A app.celery worker`
4. In terminal #3, start local SellScale API with `flask run`

## Making Feature Changes

In general, when making feature changes, follow these guidelines:

1. Make a new branch and called it `<YOUR_NAME>-<DESCRIPTION_SEPARATED_BY_UNDERSCORES>`. Examples would be `aakash-adding_delete_api_for_prospects` or `david-generate_new_hash_keys`
2. Check out the new branch, and make your feature changes.
3. Add unit tests! (Do not forget to add unit tests!)
4. Run all unit tests locally. If everything passes, push to branch.
5. Get a peer review from a fellow engineer and have them 'check it off'
6. Verify your Pull Request in Github. If things look good, merge into Master (and it will automatically deploy via our Render pipeline)

🚨 **NOTE:** 🚨
This flow is different for Migrations. Migrations are very very _very_ risky so proceed with caution. Use the Migration guide later on in this README.

## Setup SellScale API Locally

1.  Create virtual environment to install core Python dependencies.

    ```
    virtualenv -p python3 venv
    ```

2.  Step into the virtual environment.

    ```
    source venv/bin/activate
    ```

3.  Install dependencies recursively from requirements file.

    ```
    pip install -r requirements.txt
    ```

4.  Great! Now that all your dependencies are installed, you need to boot up a local database. Download [Postico 2](https://eggerapps.at/postico2/) (or your own PostgresSQL navigator of choice).
    <br/>

5.  Download [Postgres App](https://postgresapp.com/) so you can create local & testing databases.
    <br/>

6.  Using the newly installed Postgres App, create two new databases:

        - `sellscale` - Used for local testing
        - `testing` - Use for unit testing (note this one gets wiped between unit tests)

    <br/>

7.  Get a local `.env` file from a fellow engineer. It'll look something like this:
    ```
    export FLASK_APP=app.py 
    export FLASK_ENV='development' 
    export APP_SETTINGS=config.DevelopmentConfig 
    export ENCRYPTION_KEY='<KEY GOES HERE>' 
    export ISCRAPER_API_KEY='<KEY GOES HERE>' 
    export OPENAI_KEY='<KEY GOES HERE>' 
    export DATABASE_URL='postgresql://<YOUR_USER_NAME>@localhost:5432/sellscale' 
    export PHANTOMBUSTER_API_KEY='<KEY GOES HERE>' 
    export CELERY_REDIS_URL='redis://localhost:6379'
    ```

        Edit the .env file and ensure the `DATABASE_URL` is pointed to your local PostgreSQL uri.

    <br/>

8.  Get a local `.envtesting` file from a fellow engineer. This is the config used for unit tests. It will look something like this.

    ```
    export FLASK_APP=app.py
    export FLASK_ENV='testing'
    export APP_SETTINGS=config.TestingConfig
    export ENCRYPTION_KEY='<KEY GOES HERE>='
    export DATABASE_URL='postgresql://<YOUR_USER_NAME>@localhost:5432/testing'
    ```

9.  Great! Now that you have your local environment, database, and API set up, we can do a two full tests.

    - **Run Unit Tests**
      Run all the unit tests by typing `source .envtesting && python -m pytest --cov=src -vv`
      There should not be any failures.
    - **Boot Up Local API**
      Run the API locally by typing `flask run`. You can then hit the endpoints using Postman.

## Bash Profile Shortcuts

Here are some shortcuts that we find really useful to get the local and testing environment up and running quickly. Feel free to copy/paste into your local `.bash_profile`

```
alias 'pyinit'='source venv/bin/activate'
alias 'python'='python3.8'

alias ssapi='code /Users/aakash/Documents/core-SellScale/sellscale-api'
alias sssight='code /Users/aakash/Documents/core-SellScale/sellscale-sight'

alias prod='source .envprod'
alias staging='source .envstaging'
alias dev='source .env'

alias server='flask run'
alias celery='celery -A app.celery worker'
alias redis='redis-server'
```

## Running Migrations

At SellScale, our database runs on three technologies: PostgreSQL, SQLAlchemy, and Alembic.

- PostgreSQL - Our relational database of choice
- SQLAlchemy - An ORM layer over databases
- Alembic - our database versioning / migration tool of choice

In other words, we store data in a PostgreSQL database, interact with it via SQLAlchemy, and when we want to make changes to the underlying tables/databases, we use Alembic to make 'versioned changes'.

When make versioned changes, we need to be very very careful as we can permanently corrupt data and/or delete data! Best to do this in pairs unless you are certain you know what you are doing.

##### Steps:

1. Create a migration file by running `flask db migrate`
2. This will create a new file with a hash, open up the file.
3. Edit the first line of the file and ensure there's a comment describing the change. We need this so other engineers know, in human, what changes are being made to the schema.
4. Set yourself to a local environment by running `source .env` and then run `flask db upgrade`. If everything works, check a couple endpoints and ensure server is running.
5. Now checkout the testing environment by running `source .envtesting` and then run `flask db upgrade`. Run all unit tests and make sure things are passing!
6. At this point, you know the migration did not kill your local server and it did not kill unit tests, so it's most probably safe. Create a branch, and push your changes like usual. The nmerge to master.
7. SSH into a staging pod using the SSH links provided in Render. In a staging pod, run `flask db upgrade` and ensure Staging API works as expected.
8. If staging works, run it on production by SSH-ing into a production pod and running `flask db upgrade`.

Verify everything works! Do this with a pair to be cautious. Do not run migrations late at night or on Friday nights when you want to go home - usually ends in demise.
