import sys


def greeting(name: str):
    return f'Hello, {name}'


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m nsidc.granule_metgen name")
        exit(1)

    print(greeting(sys.argv[1]))
