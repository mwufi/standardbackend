from prompt_toolkit import prompt


def main():
    while True:
        text = prompt("> ")
        print("You entered:", text)


if __name__ == "__main__":
    main()
