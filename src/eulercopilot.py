import sys
import cmd_generate
import interact

args = sys.argv
user_input = args[1]


if __name__ == "__main__":
    while True:
        print(f"\033[35m用户请求:\033[0m {user_input}")
        print("\033[33mEulerCopilot:\033[0m 已经收到您的请求，正在思考答案中")

        satisfaction_query = "\033[33mEulerCopilot:\033[0m 是否继续本次服务？"
        cmd_generate.cmd_generate(user_input)
        if not interact.query_yes_or_no(satisfaction_query):
            print("\033[33mEulerCopilot:\033[0m 很高兴为您服务，下次再见～")
            sys.exit(0)
        else:
            # 用户继续提出需求：
            print("\033[33mEulerCopilot:\033[0m请继续提出您的需求：")
            user_input = sys.stdin.readline()

