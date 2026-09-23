from answer_key.parser import parse


def test_answer_key_parser_supports_common_formats():
    answers = parse("1: A\nQ2-B\n3) C\n4 -> D\n5: A/B")
    assert answers == {1: "A", 2: "B", 3: "C", 4: "D", 5: "A/B"}


def test_answer_key_parser_accepts_option_numbers_and_numerical_values_in_any_order():
    text = "1: (4), 2: (4), 25: (266), 3: (2), 23: (246), 75: (1.00), 21: (5), 24: (100)"
    answers = parse(text)
    assert answers == {
        1: "4", 2: "4", 3: "2", 21: "5", 23: "246", 24: "100",
        25: "266", 75: "1.00",
    }


def test_answer_key_parser_accepts_mixed_letter_numeric_and_compact_forms():
    text = "Q10 = (A); 7 -> 3; 18 B; 47: -2.5; 52: 6.63/10"
    answers = parse(text)
    assert answers == {7: "3", 10: "A", 18: "B", 47: "-2.5", 52: "6.63/10"}
