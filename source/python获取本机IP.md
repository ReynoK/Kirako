Title: python获取本机IP
Date: 2018-10-10 19:05:07
Category: 技术
Tag: python
============================================================
>下午在部署一位刚离职同事留下的还未上线的模块时，发现代码在获取本机IP地址（用来上报模调数据）是抛出了异常，获取本机IP也常常遇见过，遂记录之。

##### 利用驱动信息

```
import socket
import fcntl
import struct

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

print "eth0 = "+ get_ip_address('eth0')
```

利用驱动信息去获取本机IP，这种方式需要知道**本机网卡的配置名称**，对于线上环境需要同时部署多台机器的场景，机器的网卡不一定配置成`eth0`，因而可能失败。
我遇到的就是这种情况，在开发机运行是没有异常的，但现网机器没有配置`eth0`，配置的是`eth1`，因而进程启动失败。

##### 利用hostname

```
import socket
print(socket.gethostbyname(socket.gethostname()))
```

这种方式是通过本机的`hostname`去反查IP，但在机器上面`/etc/hosts`经常配置`127.0.0.1 域名`，这种情况下，获取出来的IP就是`127.0.0.1`了。

##### 利用UDP头部信息
>推荐使用该种方式

```
import socket

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip
```

生成一个UDP请求包，然后从UDP请求报中获取机器自身IP。这种方式比较优雅，不用依赖于任何信息，也不许真正的发起UDP请求。但这种方式也有缺点，就是需要申请UDP端口，会造成一定的耗时。

