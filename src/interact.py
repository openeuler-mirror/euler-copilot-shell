import sys


def query_yes_or_no(question):
    valid = {"yes": True, "y": True, "no": False, "n": False}
    prompt = " [y/n] "

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if choice == "":
            return valid["y"]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("请用 'yes' or 'no' 回答" "(or 'y' or 'n').\n")

