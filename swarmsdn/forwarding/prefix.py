import binascii
import socket

int_type_int = type(0xFF)
int_type_long = type(0xFFFFFFFFFFFFFFFF)


def ip_int_to_str(address, family):
    """Convert an integer value to an IP address string, in presentation
    format.

    address: int, integer value of an IP address (IPv4 or IPv6)
    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    """

    if family == socket.AF_INET6:
        address_len = 128
    else:
        address_len = 32
    return socket.inet_ntop(family, binascii.unhexlify(("%x" % address).zfill(address_len >> 2)))


def ip_str_to_int(address):
    """Convert an IP address string, in presentation format, to an integer.
    address:

    str, string representation of an IP address (IPv4 or IPv6)
    """

    if ":" in address:
        family = socket.AF_INET6
    else:
        family = socket.AF_INET
    return int_type_long(binascii.hexlify(socket.inet_pton(family, address)), 16)


def all_ones(n):
    """Return an int that is value the equivalent of having only the least
    significant n bits set.  Any bits more significant are not set.  This is a
    helper function for other IP address manipulation functions.

    n: int, the number of least significant bits that should be set
    """

    return 2**n - 1


def ip_prefix_mask(family, prefix_len):
    """Return prefix mask for the given address family and prefix length, as an
    int.  The prefix_len most-significant bits should be set, and the remaining
    (least significant) bits should not be set.  The total number of bits in
    the value returned should be dictated by the address family: 32 bits for
    socket.AF_INET (IPv4); 128 bits for socket.AF_INET6 (IPv6).

    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    prefix_len: int, the number of bits corresponding to the length of the
        prefix
    """
    width = 0
    if family == socket.AF_INET:
        width = 32
    elif family == socket.AF_INET6:
        width = 128
    else:
        assert False
    all_ones_mask = (1 << width) - 1
    return (((1 << width) - 1) << (width - prefix_len)) & all_ones_mask


def ip_prefix(address, family, prefix_len):
    """Return the prefix for the given IP address, address family, and
    prefix length, as an int.  The prefix_len most-significant bits
    from the IP address should be preserved in the prefix, and the
    remaining (least significant) bits should not be set.  The total
    number of bits in the prefix should be dictated by the address
    family: 32 bits for socket.AF_INET (IPv4); 128 bits for
    socket.AF_INET6 (IPv6).

    address: int, integer value of an IP address (IPv4 or IPv6)
    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    prefix_len: int, the number of bits corresponding to the length of the
        prefix
    """
    return address & ip_prefix_mask(family, prefix_len)


def ip_prefix_total_addresses(family, prefix_len):
    """Return the total number IP addresses (_including_ the first and
    last addresses within an IPv4 subnet, which cannot be used by a host
    or router on that subnet) for the given address family and prefix
    length.  The address family should be used to derive the address
    length: 32 bits for socket.AF_INET (IPv4); 128 bits for
    socket.AF_INET6 (IPv6).

    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    prefix_len: int, the number of bits corresponding to the length of the
        prefix
    """
    width = 0
    if family == socket.AF_INET:
        width = 32
    elif family == socket.AF_INET6:
        width = 128
    else:
        assert False
    return 1 << (width - prefix_len)


def ip_prefix_nth_address(prefix, family, prefix_len, n):
    """Return the nth IP address within the prefix specified with the given
    prefix, address family, and prefix length, as an int.  The prefix_len
    most-significant bits from the from the prefix should be preserved in the
    prefix, and the remaining (least significant) bits are incremented by n to
    yield an IP address within the prefix. The total number of bits in the
    prefix should be dictated by the address family: 32 bits for socket.AF_INET
    (IPv4); 128 bits for socket.AF_INET6 (IPv6).

    prefix: int, integer value of an IP prefix (IPv4 or IPv6)
    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    prefix_len: int, the number of bits corresponding to the length of the
        prefix
    n: int, the offset of the IP address within the prefix
    """

    return ip_prefix(prefix, family, prefix_len) | n


def ip_prefix_last_address(prefix, family, prefix_len):
    """Return the last IP address within the prefix specified with the given
    prefix, address family, and prefix length, as an int.  The prefix_len
    most-significant bits from the from the prefix should be preserved in the
    prefix, and the remaining (least significant) bits should all be set. The
    total number of bits in the prefix should be dictated by the address
    family: 32 bits for socket.AF_INET (IPv4); 128 bits for socket.AF_INET6
    (IPv6).

    prefix: int, integer value of an IP prefix (IPv4 or IPv6)
    family: int, either socket.AF_INET (IPv4) or socket.AF_INET6 (IPv6)
    prefix_len: int, the number of bits corresponding to the length of the
        prefix
    n: int, the offset of the IP address within the prefix
    """
    width = 0
    if family == socket.AF_INET:
        width = 32
    elif family == socket.AF_INET6:
        width = 128
    else:
        assert False
    all_ones_mask = (1 << width) - 1
    return prefix | (~ip_prefix_mask(family, prefix_len) & all_ones_mask)


class Prefix:
    """A class consisting of a prefix (int), a prefix length (int), and an
    address family (int).
    """

    def __init__(self, prefix):
        if ":" in prefix:
            family = socket.AF_INET6
        else:
            family = socket.AF_INET

        # divide the prefix and the prefix length
        prefix_str, prefix_len_str = prefix.split("/")
        prefix_len = int(prefix_len_str)

        # make sure prefix is a true prefix
        prefix_int = ip_str_to_int(prefix_str)
        prefix_int = ip_prefix(prefix_int, family, prefix_len)

        self.prefix = prefix_int
        self.prefix_len = prefix_len
        self.family = family

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "%s/%d" % (ip_int_to_str(self.prefix, self.family), self.prefix_len)

    def __contains__(self, address: str):
        """Return True if the address corresponding to this IP address is
        within this prefix, False otherwise.

        address: str, 'x.x.x.x' or 'x:x::x'
        """

        if ":" in address:
            family = socket.AF_INET6
        else:
            family = socket.AF_INET
        if family != self.family:
            raise ValueError(
                "Address can only be tested against prefix of " + "the same address family."
            )

        address = ip_str_to_int(address)

        addr_prefix = ip_prefix(address, self.family, self.prefix_len)
        return addr_prefix == self.prefix

    def __hash__(self):
        return hash((self.prefix, self.prefix_len))

    def __eq__(self, other):
        return self.prefix == other.prefix and self.prefix_len == other.prefix_len
