import sys
import boto3
import psycopg2

# ACCESS_KEY = 'AKIA6FN67KREATPJLKK4'
# SECRET_KEY = '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'

ENDPOINT="stock-screener-2.c1h93r1ybkd8.us-west-2.rds.amazonaws.com"
PORT="5432"
USR="Administrator"
REGION="us-west-2"
DBNAME="postgres"

MASTER_USERNAME = 'buffoon_squad'
MASTER_PASSWORD = 'Sharingan_Amaterasu33'


#gets the credentials from .aws/credentials
# session = boto3.Session(profile_name='dev_config')
# client = boto3.client('rds')

# token gen not working for IAM admin user -- will be using DB master user and pass for now
# token = client.generate_db_auth_token(DBHostname=ENDPOINT, Port=PORT, DBUsername=USR, Region=REGION)   

try:
    conn = psycopg2.connect(host=ENDPOINT, port=PORT, dbname=DBNAME, user=MASTER_USERNAME, password=MASTER_PASSWORD)
    cur = conn.cursor()
    cur.execute("""SELECT now()""")
    query_results = cur.fetchall()
    # cur.execute("CREATE TABLE swag (name VARCHAR PRIMARY KEY);")
    cur.execute("SELECT * FROM swag;")
    cur.fetchone()
    print(query_results)
except Exception as e:
    print("Database connection failed due to {}".format(e))   