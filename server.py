import sys
import boto3
import psycopg2

# Environment variables
ENDPOINT="stock-screener-2.c1h93r1ybkd8.us-west-2.rds.amazonaws.com"
PORT="5432"
USR="Administrator"
REGION="us-west-2"
DBNAME="postgres"

# This looks bad I know C:
MASTER_USERNAME = 'buffoon_squad'
MASTER_PASSWORD = 'Sharingan_Amaterasu33'

# Attempts to connect to database and returns connection object if successsful
# Else will throw an exception
def connect_to_postgres(): 
    try:
        return psycopg2.connect(host=ENDPOINT, port=PORT, dbname=DBNAME, user=MASTER_USERNAME, password=MASTER_PASSWORD)
    except Exception as e:
        print("Database connection failed due to {}".format(e))   