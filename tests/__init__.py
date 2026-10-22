# Test suite for Smart Bujet
import os
from src.core.config import settings

if not settings.data_encryption_key:
    settings.data_encryption_key = "a" * 64
if not settings.blind_index_secret:
    settings.blind_index_secret = "test_blind_index_secret_key_32bytes"
