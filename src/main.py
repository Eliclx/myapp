"""
一个超简单的猜数字游戏 😸
"""

import random


def main():
    print("=" * 40)
    print("  🎲 猜数字游戏  ")
    print("=" * 40)
    name = input("你叫什么名字？ ").strip() or "胖胖"
    print(f"\n你好 {name}！我心里想了一个 1~100 的数字，来猜猜看~\n")

    answer = random.randint(1, 100)
    attempts = 0

    while True:
        try:
            guess = int(input("你的猜测: "))
        except (ValueError, EOFError):
            print("输入一个数字啦！\n")
            continue

        attempts += 1
        if guess < answer:
            print("太小了 ⬆️\n")
        elif guess > answer:
            print("太大了 ⬇️\n")
        else:
            print(f"🎉 恭喜 {name}！{attempts} 次猜中！")
            break

    input("\n按回车退出...")


if __name__ == "__main__":
    main()
