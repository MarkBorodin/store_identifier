# INSTALL_APP

### Setup

clone repository:
```
git clone https://github.com/MarkBorodin/store_identifier.git
```
move to folder "store_identifier":
```
cd store_identifier
```

### run database

run on command line in the project folder:

```
docker-compose up -d
```

you need to create database. Run on command line:
```
docker-compose exec postgresql bash
```
next step:
```
su - postgres
```
next step:
```
psql
```
next step (you can create your own user, change password and other data):
```
CREATE DATABASE parsing; 
CREATE USER parsing_admin WITH PASSWORD 'parsing_adminparsing_admin';
ALTER ROLE parsing_admin SET client_encoding TO 'utf8';
ALTER ROLE parsing_admin SET default_transaction_isolation TO 'read committed';
ALTER ROLE parsing_admin SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE parsing TO parsing_admin;
ALTER USER parsing_admin CREATEDB;

```
to install the required libraries, run on command line:
```
pip install -r requirements.txt
```

to create tables run file:
```
create_db.py
```

run the program:

```
python store_identifier.py "file_name"
```
(you need to insert the file name where "file_name")

for example:

```
python main.py "example.xlsx"
```

the data will be written to the database

### ======================================================

### Finish
