def calculate_average_rating(rating_sum: int, total_reviews: int) -> float:
    if total_reviews == 0:
        return 0.0
    return round(rating_sum / total_reviews, 2)
