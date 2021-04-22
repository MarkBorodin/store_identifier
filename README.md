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
### Mods

1. counting the number of products according to the sitemap links
2. follow each link in sitemap and check keywords on each page (if no goods were found in the way 1) (using requests, since with selenium it will take much longer)
3. follow each link in sitemap and check keywords on each page (anyway)

### run the program:

```
python store_identifier.py "file_name" mode timeout
```
(you need to insert the file name where "file_name", select mode (1, 2 or 3), specify timeout (in seconds))

for example:

```
python store_identifier.py "example.xlsx" 1 360
```

the data will be written to the database and to .excel file

### ======================================================

### Finish
