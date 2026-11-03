"""Explicit invoice discounts and supplier free units; integer paise accounting."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def discount(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 <= number <= 100 or number * 100 != (number * 100).to_integral_value():
            raise ValueError('Discount must be 0–100 percent with at most two decimal places')
        return int(number * 100)
    except InvalidOperation:
        raise ValueError('Invalid discount percentage')


def terms(item, kind):
    bps = discount(item.get('discount_percent', 0))
    raw = item.get('free_qty', 0)
    try:
        free = int(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Free quantity must be a non-negative whole number of loose units')
    if str(free) != str(raw) or not 0 <= free <= 1000000000:
        raise ValueError('Free quantity must be a non-negative whole number of loose units')
    if free and kind != 'purchase':
        raise ValueError('Free quantities are supported only on purchase receipts')
    if kind in ('return', 'purchase_return') and bps:
        raise ValueError('Returns use the original invoice discount allocation')
    return bps, free


def amounts(price, paid_qty, tax, inclusive, bps):
    rounded = lambda amount: int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    basis = rounded(Decimal(price * paid_qty) * (10000 - bps) / 10000)
    if inclusive:
        total = basis
        taxable = rounded(Decimal(total) / (1 + Decimal(tax) / 10000))
    else:
        taxable = basis
        total = rounded(Decimal(taxable) * (1 + Decimal(tax) / 10000))
    return taxable, total
