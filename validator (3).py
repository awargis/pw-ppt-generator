from models import ProcessingReport


def validate_regions(regions, answers=None):
    report = ProcessingReport(questions=len(regions))
    seen = set()
    for region in regions:
        report.subject_counts[region.subject] = report.subject_counts.get(region.subject, 0) + 1
        if region.number in seen:
            report.warnings.append(f"Duplicate question number: {region.number}")
        seen.add(region.number)
        if region.confidence < 0.60:
            region.needs_review = True
            report.low_confidence.append(region.number)
    if answers is not None:
        report.missing_answers = sorted(seen - set(answers))
    return report
