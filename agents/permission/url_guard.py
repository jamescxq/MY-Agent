import ipaddress
import socket
from urllib.parse import urlsplit

# 网址门禁：读网页的工具是在这台电脑上联网的，所以要先看这个网址能不能去。
# 和 guard.py 是一对：guard.py 管"这个文件路径能不能碰"，这里管"这个网址能不能访问"。
#
# 要挡的是"内网地址"：127.0.0.1（这台电脑自己）、192.168.x.x 和 10.x.x.x（家里或公司的局域网，
# 路由器的管理页面就在这里）、169.254.169.254（云服务器上能读到密钥的地址）。
# 网页里的一句话就可能骗模型去读这些地址，再把读到的内容带出去。这种攻击叫 SSRF。
#
# 做法：先把网址里的域名查成 IP，只要有一个 IP 落在内网里就拒绝；查不出来也拒绝（宁可不读，不冒险）。
# 说明：这里查了一次，真正连接时系统还会再查一次，两次之间域名换了指向的话拦不住。
# 彻底的做法是连接时钉死查到的 IP，现在没做。


def blocked_ip(text):
    """这个 IP 是不是不该访问的：内网、这台电脑自己、局域网自动分配的、保留的。"""
    ip = ipaddress.ip_address(text)
    mapped = getattr(ip, "ipv4_mapped", None)       # ::ffff:127.0.0.1 这种写法，里面包着一个 IPv4
    if mapped is not None:
        ip = mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def safe_url(url, resolve=socket.getaddrinfo):
    """这个网址能不能访问。返回 (能不能, 不能的原因)。

    resolve 是"把域名查成 IP"的函数，平时不用传；测试时传一个假的，不用真的去查。
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False, "网址写得不对"
    if parts.scheme not in ("http", "https"):
        return False, "只能访问 http 或 https 开头的网址"
    if not parts.hostname:
        return False, "网址里没有域名"
    if parts.username or parts.password:
        return False, "网址里不能带用户名和密码"
    try:
        found = resolve(parts.hostname, None)
    except OSError:
        return False, f"查不到 {parts.hostname} 这个域名"
    addresses = {item[4][0] for item in found}
    if not addresses:
        return False, f"查不到 {parts.hostname} 这个域名"
    for address in addresses:
        if blocked_ip(address):
            return False, f"{parts.hostname} 指向内网地址，不能访问"
    return True, ""


if __name__ == "__main__":
    def fake_dns(table):                             # 假的查询：按表回答，表里没有的当作查不到
        def resolve(host, port):
            if host not in table:
                raise OSError("查不到")
            return [(None, None, None, "", (ip, 0)) for ip in table[host]]
        return resolve

    dns = fake_dns({
        "example.com": ["93.184.216.34"],
        "evil.test": ["127.0.0.1"],                  # 域名看着正常，其实指向这台电脑自己
        "half.test": ["93.184.216.34", "10.0.0.5"],  # 两个 IP 里有一个是内网的
        "127.0.0.1": ["127.0.0.1"], "192.168.1.1": ["192.168.1.1"], "169.254.169.254": ["169.254.169.254"],
        "localhost": ["127.0.0.1"], "[::1]": ["::1"], "::1": ["::1"],
    })
    for url in (
        "https://example.com/a?b=1",                 # 应该：能
        "http://127.0.0.1:8000/",                    # 应该：不能，这台电脑自己
        "http://localhost/",                         # 应该：不能
        "http://192.168.1.1/admin",                  # 应该：不能，路由器
        "http://169.254.169.254/latest/meta-data/",  # 应该：不能，云服务器的密钥地址
        "http://[::1]/",                             # 应该：不能，IPv6 写法的这台电脑自己
        "https://evil.test/",                        # 应该：不能，域名指向内网
        "https://half.test/",                        # 应该：不能，有一个 IP 是内网的
        "https://nowhere.test/",                     # 应该：不能，查不到
        "file:///E:/MY-Agent/config.py",             # 应该：不能，不是 http
        "ftp://example.com/",                        # 应该：不能
        "https://user:pass@example.com/",            # 应该：不能，带了用户名密码
        "不是网址",                                   # 应该：不能
    ):
        print(safe_url(url, dns), url)
