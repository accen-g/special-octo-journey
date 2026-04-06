import oracledb

conn = oracledb.connect(
    user='bic_ccd',
    password='bic_ccd_pass',
    dsn='localhost:1521/XEPDB1'
)

print('Oracle version:', conn.version)

conn.close()