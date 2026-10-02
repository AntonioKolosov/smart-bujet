from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from typing import List, Dict, Any, Optional


class DiscountDistributor:
    @staticmethod
    def distribute(
        items: List[Dict[str, Any]],
        discount_percent: Optional[float] = None,
        discount_amount: Optional[float] = None,
        total_paid: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Deterministically distributes discount across expense items using the Largest Remainder Method (Hamilton Algorithm).
        Reconciles every penny/tiyn so sum(item.amount) == total_paid.
        """
        if not items:
            return []

        # Only apply discount to expense items with amount > 0
        expense_indices = [
            i for i, item in enumerate(items)
            if item.get("type", "expense") == "expense" and Decimal(str(item.get("amount", 0) or 0)) > Decimal("0")
        ]

        if not expense_indices:
            return items

        # Calculate sum of pre-discount expense items
        base_sum = sum(Decimal(str(items[i].get("amount", 0))) for i in expense_indices)

        # Determine target discount
        discount_val = Decimal("0")

        if total_paid is not None:
            try:
                t_paid = Decimal(str(total_paid))
                if Decimal("0") < t_paid < base_sum:
                    discount_val = base_sum - t_paid
            except Exception:
                pass

        if discount_val <= Decimal("0") and discount_amount is not None:
            try:
                d_amt = Decimal(str(discount_amount))
                if Decimal("0") < d_amt < base_sum:
                    discount_val = d_amt
            except Exception:
                pass

        if discount_val <= Decimal("0") and discount_percent is not None:
            try:
                pct = Decimal(str(discount_percent))
                if Decimal("0") < pct < Decimal("100"):
                    discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except Exception:
                pass

        if discount_val <= Decimal("0"):
            return items

        # Largest Remainder Method
        exact_discounts = []
        floor_discounts = []
        remainders = []

        for idx in expense_indices:
            item_amt = Decimal(str(items[idx].get("amount", 0)))
            exact_d = discount_val * (item_amt / base_sum)
            floor_d = (exact_d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_FLOOR) / Decimal("100")
            rem = exact_d - floor_d

            floor_discounts.append(floor_d)
            remainders.append((rem, item_amt, idx))

        allocated_base = sum(floor_discounts)
        unallocated_cents = int(((discount_val - allocated_base) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # Sort remainders descending by remainder, then by item amount
        remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)

        final_discounts: Dict[int, Decimal] = {}
        for rank, (rem, item_amt, idx) in enumerate(remainders):
            bonus = Decimal("0.01") if rank < unallocated_cents else Decimal("0")
            item_pos = expense_indices.index(idx)
            final_discounts[idx] = floor_discounts[item_pos] + bonus

        # Build resulting items
        results = []
        for i, item in enumerate(items):
            item_copy = dict(item)
            if i in final_discounts:
                orig = Decimal(str(item.get("amount", 0)))
                disc = final_discounts[i]
                final_amt = orig - disc
                item_copy["amount"] = float(final_amt)
                item_copy["original_amount"] = float(orig)
                item_copy["discount_amount"] = float(disc)
            results.append(item_copy)

        return results
