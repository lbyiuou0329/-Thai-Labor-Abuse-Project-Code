import os
import logging
import mysql.connector

import pandas as pd

from mysql.connector import Error
from configparser import ConfigParser
from pandas.io.sql import pandasSQL_builder


CFG_DBHOST = 'dbhost'
CFG_DBPORT = 'dbport'
CFG_DBNAME = 'dbname'
CFG_DBUSER = 'dbuser'
CFG_DBPASSWORD = 'dbpwd'
DEFAULT_INI = r'/Users/boyuliu/pyprojects/Joann/Joann-Thailand-Project/local/database.ini'

def Config(filename=DEFAULT_INI, section='mysql_local'):
    """
    creates a dict for connecting to postgresql
    Args:
        filename (str): must be an ini file, contains a section for section
        section (str): which section of the ini file to read
    Returns:
        dictionary with all fields defined in the specified section of the file
    """
    # create a parser
    parser = ConfigParser()
    # read config file
    try:
        parser.read(filename)
    except Exception as e:
        logging.error('Error loading default config file {ini}, message: \n {msg}'.format(ini=DEFAULT_INI, msg=str(e)))
        raise RuntimeError(str(e))

    # get section, default to postgresql
    config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            config[param[0]] = param[1]
        if 'raise_on_warnings' in config:
            config['raise_on_warnings'] = eval(config['raise_on_warnings'])
    else:
        cwd = os.getcwd()
        raise Exception('Section {0} not found in the {1} file at {2}'.format(section, filename, cwd))

    return config

class DbProxy:
    # db utils
    if not os.path.isfile('log/mysql_db.log'):
        os.makedirs('log')
        with open('log/mysql_db.log', 'w') as fp:
            pass
    logging.basicConfig(
        format='[%(asctime)s.%(msecs)d %(levelname)-8s %(filename)s:%(lineno)d] %(message)s',
        datefmt='%d-%m-%Y:%H:%M:%S',
        level=logging.DEBUG,
        filename='log/mysql_db.log')

    def __init__(self, config):
        """
        mainly stores all required parameters to start a connection, but does not
        connect to db. Each query should connect to db and close connection immediately
        afterwards
        Args:
            host (str): db host
            port (int): db port
            dbname (str): db name
            user (str): db username
            pwd (str): db password
        """
        if 'host' not in config or 'database' not in config or 'user' not in config or 'password' not in config:
            logging.error('required db settings not found')
            raise RuntimeError('required db settings not found')
        self.config = config
        self.connection = None

    @staticmethod
    def create_from_config(config=None):
        """
        creates DbProxy object from config file instead of parameters
        Args:
            config (dict):has the following fields, used to specify postgresql connection
                CFG_DBHOST
                CFG_DBPORT
                CFG_DBNAME
                CFG_DBUSER
                CFG_DBPASSWORD
        Returns:
            DbProxy object
        """
        if config is None:
            config = Config()
        #import pdb; pdb.set_trace()
        return DbProxy(config)

    def get_db_connection(self):
        """
        connects to postgresql db
        Returns:
            a psycopg2 connection object if succeeds, None if fails (raises RunTimeError)
        """
        if self.connection is not None:
            return self.connection

        try:
            # connect to the PostgreSQL server
            logging.info('Connecting to the MySQL database...')
            conn = mysql.connector.connect(**self.config)
            return conn
        except (Exception) as error:
            logging.error('Failed to connect to db \n %s' % str(error))
            raise RuntimeError((str(error)))

    def execute_statement(self, sql, str_values=None, connection=None):
        """
        execute sql statement that does not return things
        Args:
            sql (str): sql string, can have string formatter (e.g. %s)
            connection (psycopg2 connection object): optional
        Returns:
            None
        """
        if self.connection is not None:
            conn = self.connection
        elif connection is not None:
            conn = connection
        else:
            conn = self.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, str_values)
            row_count = cur.rowcount
            # close communication with the PostgreSQL database server
            cur.close()
            conn.commit()

        except (Exception) as e:
            logging.error('Failed to execute query \n %s' % str(e))
            raise e

        finally:
            if conn is not None and conn is not self.connection:
                try:
                    conn.close()
                except:
                    pass
        return row_count

    def execute_query(self, sql, str_values=[], connection=None, chunksize=None, return_generator=False):
        """ Executes sql query and returns a pandas DataFrame from the result.
        Args:
            sql: (str) sql string, can have string formatter (e.g. %s)
            str_values: (str) parameters to pass into sql
            connection: (psycopg2 connection object) optional
            chunksize: (int)
            return_generator: (bool)
        Returns:
            pandas dataframe
        """
        if (chunksize is None) and return_generator:
            raise Exception('In order to return a generator you must use a non-null chunksize')
        if self.connection is not None:
            conn = self.connection
        elif connection is not None:
            conn = connection
        else:
            conn = self.get_db_connection()

        if return_generator or chunksize is None:
            out = pd.read_sql(sql, conn, params=str_values, chunksize=chunksize)
            return out

        cur = conn.cursor()
        psql = pandasSQL_builder(cur, is_cursor=True)
        df = psql.read_query(sql, params=str_values, chunksize=chunksize)
        columns = [col_desc[0] for col_desc in cur.description]
        df_out = None
        while True:
            try:
                df_out = pd.concat([df_out, next(df)], ignore_index=True)
            except StopIteration:
                break
        if df_out is None:
            df_out = pd.DataFrame(columns=columns)
        if connection is None and conn is not self.connection:
            conn.close()
        return df_out

    def test_connection(self):
        """ test connection, prints the version of postgresql
        Returns:
            none
        """
        sql = "select database();"
        print(self.execute_query(sql))


def get_db_proxy(config=None):
    """
    util, get database proxy object, should be the only thing imported by another module
    usage: from db import get_db_proxy
    Args:
        config (dict): has the following fields, used to specify postgresql connection
            CFG_DBHOST
            CFG_DBPORT
            CFG_DBNAME
            CFG_DBUSER
            CFG_DBPASSWORD
    Returns:
        DbProxy object
    """
    return DbProxy.create_from_config(config=config)

if __name__=='__main__':
    db = get_db_proxy()
    db.test_connection()

# try:
#     connection = mysql.connector.connect(**config)
#     if connection.is_connected():
#         db_Info = connection.get_server_info()
#         print("Connected to MySQL Server version ", db_Info)
#         cursor = connection.cursor()
#         cursor.execute("select database();")
#         record = cursor.fetchone()
#         print("Your connected to database: ", record)
# except Error as e:
#     print("Error while connecting to MySQL", e)
#     raise
# finally:
#     if (connection.is_connected()):
#         cursor.close()
#         connection.close()
#         print("MySQL connection is closed")
