import atexit
from argparse import ArgumentParser

from swarmsdn.network import AdHocNetwork


def get_parser():
    parser = ArgumentParser(
        prog="Mininet Ad-hoc network testing program",
        description="Starts a mininet ad-hoc simulation that connects to an existing controller",
    )
    parser.add_argument("-t", "--timesteps", type=int, default=10)
    parser.add_argument("-s", "--seed", type=int, default=1)
    parser.add_argument("--starting-links", type=int)
    parser.add_argument("--dynamic-links", type=int)
    parser.add_argument("--controller-ip", type=str, default="127.0.0.1")
    parser.add_argument("-c", "--host-count", type=int, required=True)
    parser.add_argument("data_basename", type=str)
    return parser


def main():
    args = get_parser().parse_args()
    starting_links = (args.host_count // 2) if args.starting_links is None else args.starting_links
    dynamic_links = (args.host_count // 2) if args.dynamic_links is None else args.dynamic_links

    net = AdHocNetwork(
        data_log_base=args.data_basename,
        time_steps=args.timesteps,
        seed=args.seed,
        host_cnt=args.host_count,
        starting_links=starting_links,
        dynamic_links=dynamic_links,
        controller_ip=args.controller_ip,
    )
    atexit.register(net.stop_net)
    net.run()


if __name__ == "__main__":
    main()
