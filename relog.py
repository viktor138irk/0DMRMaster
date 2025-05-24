import argparse

from udpproxylogger import log_packet, setup_logger


def parse_arguments():
    parser = argparse.ArgumentParser(description='ReLog')
    parser.add_argument('infilename', type=str, help='input log filename')
    parser.add_argument('-l', '--log-file', type=str, help='Log filename')
    return parser.parse_args()


def main():
    args = parse_arguments()
    setup_logger(args.log_file)

    with open(args.infilename, "r") as file:
        for line in file:
            line = line.strip()
            if line.startswith("HD: "):
                pdata = bytes.fromhex(line[4:])
                log_packet("DIR", pdata, ('', ''))


if __name__ == "__main__":
    main()
