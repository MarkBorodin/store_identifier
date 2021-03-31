# INSTALL_APP

### Setup

clone repository:
```
git clone https://github.com/MarkBorodin/google_my_business.git
```
move to folder "google_my_business":
```
cd google_my_business
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

if you need to get data from one company, run on command line:

```
python main.py "company_name"
```
(you need to insert the company name where "company_name")
for example:

```
python main.py "Ad5 GmbH"
```

the data will be written to the database

### ======================================================

if you need to get data from all companies at once from a file, run on command line:
```
python main_serial.py "file_name"
```
(you need to insert the file name where "file_name")
for example:

```
python main.py "Zefix-Crawl-Test.xlsx"
```
Сompany names should be in the first column.
The data will be written to the database

### Finish
