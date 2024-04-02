import json
import shlex
import interact
import requests
import os


def cmd_generate(question):
    endpoint = "https://rag.test.osinfra.cn/kb/shell"

    data = {"question": question}
    try:
        res = requests.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=data,
            stream=False
        )
        result = res.json()
    except Exception as _:
        return None

    shell = os.environ.get("SHELL", "/bin/sh")
    ans = result.get("answer", None)
    try:
        ans = json.loads(ans)
    except Exception as _:
        return None
    for cmd in list(ans.values()):
        print(cmd)

    if interact.query_yes_or_no("\033[33mEulerCopilot:\033[0m 是否执行以上命令？"):
        for cmd in list(ans.values()):
            full_command = f"{shell} -c {shlex.quote(cmd)}"
            os.system(full_command)

