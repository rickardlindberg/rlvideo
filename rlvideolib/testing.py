def doctest_absent(text, item):
    if item not in text:
        print("Yes")
    else:
        print(f"{item} found in text:")
        print(text)
