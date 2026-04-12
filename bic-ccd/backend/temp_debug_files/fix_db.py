import os
from sqlalchemy import create_engine, text
from app.config import get_settings

def run():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    out = []
    with engine.connect() as conn:
        rs = conn.execute(text("SELECT column_name FROM all_tab_columns WHERE table_name = 'KRI_CONFIGURATION'"))
        columns = [row[0] for row in rs]
        out.append("ACTUAL COLUMNS IN ORACLE: " + str(columns))

    try:
        from app.database import SessionLocal
        from app.models import KriConfiguration
        db = SessionLocal()
        cfg = db.query(KriConfiguration).first()
        out.append("Success! " + str(cfg))
    except Exception as e:
        import traceback
        out.append("ERROR:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))

    with open("oracle_debug.txt", "w") as f:
        f.write("\n".join(out))
    print("Done. Look at oracle_debug.txt")

if __name__ == '__main__':
    run()
