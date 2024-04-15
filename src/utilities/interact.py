# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

def query_yes_or_no(question: str) -> bool:
    valid = {"yes": True, "y": True, "no": False, "n": False}
    prompt = " [Y/n] "

    while True:
        choice = input(question + prompt).lower()
        if choice == "":
            return valid["y"]
        elif choice in valid:
            return valid[choice]
        else:
            print('请用 "yes (y)" 或 "no (n)" 回答')
