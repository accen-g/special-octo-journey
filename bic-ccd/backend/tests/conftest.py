"""BIC-CCD Backend Test Suite."""
import os
os.environ["USE_SQLITE"] = "true"
os.environ["SQLITE_URL"] = "sqlite:///./test_bic_ccd.db"
os.environ["JWT_SECRET"] = "test-secret"
