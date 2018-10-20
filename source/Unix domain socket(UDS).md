Title: Unix domain socket(UDS)
Date: 2018-10-18 23:16:19
Category: 技术
Tag: Linux
============================================================
Write description here...

>最近在搭建`Nginx`+`Gunicorn`的时候，返现这两个进程可以通过一个后缀为`.sock`的文件进行进程之间的通讯，之前遇到的大多数都是通过管道或TCP连接进行通讯，因此花了点时间研究一下。

`Nginx`中有一段配置是这样的：

```ini
  upstream app_server {
    # fail_timeout=0 means we always retry an upstream even if it failed
    # to return a good HTTP response

    # for UNIX domain socket setups
    server unix:/tmp/gunicorn.sock fail_timeout=0;

    # for a TCP configuration
    # server 192.168.0.7:8000 fail_timeout=0;
  }
```

`Unix domain unix`称为网络套接字，简称UDS，是基于`Socket API`的基础上发展而来的，`Socket API`原本适用于不同机器上进程间的通讯，当然也可用于同一机器上不同进程的通讯（通过localhost），后来在此基础上，发展出专门用于进程间通讯的IPC机制，UDS与原来的网络Socket相比，仅仅只需要在进程间复制数据，无需处理协议、计算校验和、维护序号、添加和删除网络爆头、发送确认报文，因此更高效，速度更快。UDS提供了和TCP/UDP类似的流和数据包，但这两种都是可靠的，消息不会丢失也不会乱序。

<!--more-->

UDS的创建与网络Socket的创建类似：
1. 创建一个`Socket`，指定`family`为`AF_UNIX`，`type`支持`SOCK_STRAEM`和`SOCK_DGRAM`两种；
2. `bind`地址，与网络Socket不同，UDS所绑定的对象是一个文件；
3. 开始监听`accept`；
4. 接收请求`accept`，为每个连接建立新的套接字，并从监听队列队列中移除。

下面是一个python写的echo服务器端演示代码：

```
import socket
import os

server_address = "/Users/Temp/socket.sock"

if os.path.exists(server_address):
    raise Exception("The sock file is exist")

server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server_socket.bind(server_address)
server_socket.listen(1)

try:
    while True:
        print("Start accept!")

        client_socket,client_address = server_socket.accept()
        
        while True:
            print("Connect from:", client_address)

            data = client_socket.recv(1024)
            if not data:
                print("Connection closed by client!\n")
                break
            else:
                print("Received:", data)
                print("Send back:", client_socket.sendall(data))

    os.unlink(server_address)
except Exception as e:
    print(e)
    if os.path.exists(server_address):
        os.unlink(server_address)
```

UDS的客户端和网络Socket一样，只不过`connect`的是一个文件，如下是pyrhon写的客户端演示代码：

```
import socket
import os
import time

server_address = "/Users/Temp/socket.sock"

if not os.path.exists(server_address):
    raise Exception("The sock file is not exist")

print("Connect to socket:", server_address)
client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    client_socket.connect(server_address)
except Exception as e:
    print(e)
    raise


def send_test(client_socket, send_data):
    time.sleep(1)
    print("Send:", send_data)
    client_socket.send(send_data)
    time.sleep(1)
    recv_data = client_socket.recv(1024)
    print("Echo:", recv_data)


print("Start communication!")
send_data = b"Hello, world!"
send_test(client_socket, send_data)
send_data = b"My name is Tom!"
send_test(client_socket, send_data)
print("Close connection!")
client_socket.close()
```

运行结果如下：

```
Connect to socket: /Users/Temp/socket.sock
Start communication!
Send: b'Hello, world!'
Echo: b'Hello, world!'
Send: b'My name is Tom!'
Echo: b'My name is Tom!'
Close connection!
```

还有一种简单的方式可以快速的创建非命名的匿名UDS(类似于管道)，利用函数`socket.socketpair([family[, type[, proto]]])`，但这种方式通用性不强，只能用于父子进程之间使用，无法在无关进程中使用。

