# Spino

A micro sequencing libraries management system.

## Running Spino

Spino requires Python2 and the MySQLdb and tornado packages.

The `config.py` file has to be modified to define the directory of uploaded files (TapeStation reports, etc.).

To start Spino, run the following command:

    $ python spino.py --dbhost=HOST --dbname=DATABASE --dbuser=USER --dbpasswd=PASSWORD [--debug] [--port=PORT]
    
