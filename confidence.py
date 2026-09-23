def score_region(region) -> float:
    """Combine detector confidence and geometry into a review score."""
    text_score = max(0.0, min(1.0, region.confidence))
    height_score = min(1.0, region.box.height / 140.0)
    width_score = min(1.0, region.box.width / 500.0)
    score = 0.65 * text_score + 0.20 * height_score + 0.15 * width_score
    return round(max(0.0, min(1.0, score)), 3)
