from app.services.margin import calculate_margin, validate_margin


def test_margin_calculator_uses_all_costs_and_rounding():
    result = calculate_margin(
        sale_price=100,
        purchase_price=50,
        delivery=8.99,
        commission_rate=0.15,
        other_fees=2,
        tax_rate=0.02,
    )
    assert result.commission == 15.0
    assert result.taxes == 2.0
    assert result.profit == 22.01
    assert result.roi == 28.22
    assert validate_margin(result, 20, 20).state == "PASS"
    assert validate_margin(result, 30, None).state == "FAIL"
