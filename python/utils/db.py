import psycopg2
import psycopg2.extras
import pandas as pd
from utils.config import DB_CONFIG, DATA_POWERBI


def connect():
    cfg = dict(DB_CONFIG)
    try:
        return psycopg2.connect(**cfg)
    except psycopg2.OperationalError:
        admin = psycopg2.connect(host=cfg["host"], port=cfg["port"],
                                 dbname="postgres", user=cfg["user"],
                                 password=cfg["password"])
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE {cfg["dbname"]}')
        admin.close()
        return psycopg2.connect(**cfg)


def run_query(sql, params=None):
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql, params=None, many_params=None):
    with connect() as conn:
        with conn.cursor() as cur:
            if many_params is not None:
                psycopg2.extras.execute_values(cur, sql, many_params)
            else:
                cur.execute(sql, params)
        conn.commit()


def copy_from_df(df, table, columns):
    with connect() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s",
                [tuple(row) for row in df[columns].itertuples(index=False, name=None)],
            )
        conn.commit()


def export_powerbi(df, name):
    out = DATA_POWERBI / f"{name}.csv"
    df.to_csv(out, index=False)
    return out