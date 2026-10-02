import hashlib
import hmac
import time
from urllib.parse import parse_qsl

def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        
        if "auth_date" not in parsed_data:
            return None
            
        auth_date = int(parsed_data["auth_date"])
        if time.time() - auth_date > 86400:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            return parsed_data
            
        return None
    except Exception:
        return None
