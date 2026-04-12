import sys, traceback
try:
    from app.main import seed_database
    seed_database()
    print('SEED COMPLETED FULLY!')
except Exception as e:
    with open('seed_error.txt', 'w') as f:
        f.write("".join(traceback.format_exception(type(e), e, e.__traceback__)))
    print("Failed. Look at seed_error.txt")
