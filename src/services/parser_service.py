import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

def parse_amount(text: str) -> Optional[Tuple[Decimal, str]]:
    text_clean = text.replace(" ", "")
    # Find decimal numbers or integers
    match = re.search(r"(\d+(?:\.\d+)?)", text_clean)
    if not match:
        return None
        
    try:
        amount = Decimal(match.group(1))
        # Remove matched number from original text to leave the description
        description = re.sub(r"(\d+(?:[\s\.]\d+)?)", "", text).strip()
        return amount, description
    except InvalidOperation:
        return None
