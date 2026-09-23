def validate(questions, answers):
    numbers = {q.number for q in questions}
    answer_numbers = set(answers or {})
    return {
        "missing": sorted(numbers - answer_numbers),
        "unused": sorted(answer_numbers - numbers),
    }
