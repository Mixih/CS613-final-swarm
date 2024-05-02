import os
import atexit

from swarmsdn.networks import AdHocNetwork


RAND_SEED = 1


def main():
    net = AdHocNetwork(10, RAND_SEED, 20, 5, 20, "localhost")
    atexit.register(net.stop_net)
    net.run()


if __name__ == "__main__":
    main()
