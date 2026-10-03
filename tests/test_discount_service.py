import unittest
from decimal import Decimal
from src.services.discount_service import DiscountDistributor


class TestDiscountDistributor(unittest.TestCase):
    def test_discount_distributor_fixed_amount(self):
        items = [
            {"item_name": "Рыба", "amount": 4032.0, "type": "expense"},
            {"item_name": "Хлеб", "amount": 950.0, "type": "expense"},
        ]
        # Total before discount: 4982. Discount: 249. Total paid: 4733.
        result = DiscountDistributor.distribute(items, discount_amount=249.0)

        self.assertEqual(len(result), 2)
        total_after = sum(Decimal(str(item["amount"])) for item in result)
        self.assertEqual(total_after, Decimal("4733.00"))
        self.assertEqual(result[0]["original_amount"], 4032.0)
        self.assertEqual(result[1]["original_amount"], 950.0)

    def test_discount_distributor_total_paid(self):
        items = [
            {"item_name": "Товар 1", "amount": 100.0, "type": "expense"},
            {"item_name": "Товар 2", "amount": 100.0, "type": "expense"},
            {"item_name": "Товар 3", "amount": 100.0, "type": "expense"},
        ]
        # 300 base, 250 paid -> 50 discount distributed across 3 items
        result = DiscountDistributor.distribute(items, total_paid=250.0)

        self.assertEqual(len(result), 3)
        total_after = sum(Decimal(str(item["amount"])) for item in result)
        self.assertEqual(total_after, Decimal("250.00"))

    def test_discount_distributor_empty_or_no_discount(self):
        items = [{"item_name": "Кофе", "amount": 1500.0, "type": "expense"}]
        result = DiscountDistributor.distribute(items, discount_amount=0.0)
        self.assertEqual(result, items)


if __name__ == "__main__":
    unittest.main()
