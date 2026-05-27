def calculate_legs(width):

    # мінімум 4

    if width <= 900:
        return 4

    elif width <= 1600:
        return 6

    else:
        return 8