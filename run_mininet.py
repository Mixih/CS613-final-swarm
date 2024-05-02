import atexit

from swarmsdn.network import AdHocNetwork


RAND_SEED = 1


def main():
    net = AdHocNetwork(10, RAND_SEED, 20, 5, 20, "127.0.0.1")
    atexit.register(net.stop_net)
    net.run()


if __name__ == "__main__":
    main()
