# diglinplus
Scripts for DigLin+ data processing and analysis

## Instructions
- Clone this repo `git clone git@github.com:timjzee/diglinplus.git`
- `pip install -r requirements.txt` in a virtual environment
- Ask the project supervisor for the connection string and create a `.env` file:
```
# MongoDB connection string
CONNECT_STR=mongodb://yourconnectionstring
```
- If you want to continue development of this repo you should probably get a local copy of the database, so you're not constantly pulling the entire database over the internet:
    - `mongodump --uri "mongodb://yourconnectionstring" --out "/path/to/databaseDump"`
    - `mongorestore --db nameForLocalDB /path/to/databaseDump/nameOfRemoteDB`
    - don't forget to change `.env` file: `CONNECT_STR=mongodb://localhost:27017/nameForLocalDB` (27017 is the default port)
- start local mongodb server `brew services start mongodb-community@6.0`
- now you can run `diglin.py`