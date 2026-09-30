"""Database access shared by HTTP and isolated media processes."""

import os

import psycopg
from psycopg.rows import dict_row


def database():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
