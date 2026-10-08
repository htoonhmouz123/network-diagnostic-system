"""Console helper so messages from different threads never get mixed on one line."""


def log_message(message):
    # one single write() call (newline included) keeps the line in one piece
    print(message + "\n", end="", flush=True)
