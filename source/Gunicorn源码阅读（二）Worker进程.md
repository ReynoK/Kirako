Title: Gunicorn源码阅读（二）Worker进程
Date: 2018-10-16 22:50:33
Category: 技术
Tag: python
============================================================

>Gunicorn.worker实现了不同类型的work进程，有单进程、多线程、多协程等形式。
<!--more-->

`gunicorn.worker`目录结构：

```
workers/
├── __init__.py
├── _gaiohttp.py
├── base.py
├── base_async.py
├── gaiohttp.py
├── geventlet.py
├── ggevent.py
├── gthread.py
├── gtornado.py
├── sync.py
└── workertmp.py
```

主要看以下几个源码文件
1. `base.py`：基类文件
2. `gthread.py`：单进程多线程工作模式
3. `sync.py`：单进程单线程模式
4. `workertmp`：tmp文件，master监控worker进程的机制

剩下的其他文件大同小异。

####Worker

下面是将`Worker`类实现的简略。

```
class Worker(object):
    SIGNALS = [getattr(signal, "SIG%s" % x)
            for x in "ABRT HUP QUIT INT TERM USR1 USR2 WINCH CHLD".split()] # 支持的信号

    PIPE = []

    def __init__(self, age, ppid, sockets, app, timeout, cfg, log)
    def __str__(self)
    def notify(self)
    def run(self)
    def init_process(self)
    def load_wsgi(self)                  # 获得实现wsgi协议的app，如Flask
    def init_signals(self)
    def handle_usr1(self, sig, frame)
    def handle_exit(self, sig, frame)
    def handle_quit(self, sig, frame)
    def handle_abort(self, sig, frame)
    def handle_error(self, req, client, addr, exc)
    def handle_winch(self, sig, fname)
```

![Worker调用过程](https://upload-images.jianshu.io/upload_images/6201701-52d9e40d997c96da.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


```python
    def __init__(self, age, ppid, sockets, app, timeout, cfg, log):
        """\
        This is called pre-fork so it shouldn't do anything to the
        current process. If there's a need to make process wide
        changes you'll want to do that in ``self.init_process()``.
        """
        self.age = age
        self.pid = "[booting]"
        self.ppid = ppid
        self.sockets = sockets
        self.app = app                      
        self.timeout = timeout  #超时时间
        self.cfg = cfg              # 配置
        # 状态
        self.booted = False  #已启动
        self.aborted = False  #已终止

        self.reloader = None  

        self.nr = 0
        jitter = randint(0, cfg.max_requests_jitter)
        self.max_requests = cfg.max_requests + jitter or sys.maxsize
        self.alive = True           # 是否存活
        self.log = log                #日志对象
        self.tmp = WorkerTmp(cfg)  # worker tmp文件
```

`__init__()`做的事情相对简单，就是将一些相关的参数，如`cfg`、`app`等作为`Worker`对象的属性，同时创建一个`tmpfile`，**父进程通过检查该文件的时间戳，来确认子进程是否存活。**

```
def notify(self):
        """\
        Your worker subclass must arrange to have this method called
        once every ``self.timeout`` seconds. If you fail in accomplishing
        this task, the master process will murder your workers.
        """
        self.tmp.notify()
```
`notify()`调用`WorkerTmp.notify()`更改所对应tmp文件的时间戳。

```
    def init_process(self):
        """\
        If you override this method in a subclass, the last statement
        in the function should be to call this method with
        super(MyWorkerClass, self).init_process() so that the ``run()``
        loop is initiated.
        """

        # set environment' variables
        if self.cfg.env:
            for k, v in self.cfg.env.items():
                os.environ[k] = v
        #设置进程信息
        util.set_owner_process(self.cfg.uid, self.cfg.gid,
                               initgroups=self.cfg.initgroups)

        # Reseed the random number generator
        util.seed()

        # For waking ourselves up
        self.PIPE = os.pipe()
        for p in self.PIPE:
            util.set_non_blocking(p)
            util.close_on_exec(p)

        # Prevent fd inheritance
        # close_on_exec 设置对应的文件在创建子进程的时候不会被继承
        for s in self.sockets:
            util.close_on_exec(s)
        util.close_on_exec(self.tmp.fileno())

        self.wait_fds = self.sockets + [self.PIPE[0]]

        self.log.close_on_exec()

        # 设置信号处理函数
        self.init_signals()

        # start the reloader
        if self.cfg.reload:
            def changed(fname):
                self.log.info("Worker reloading: %s modified", fname)
                self.alive = False
                self.cfg.worker_int(self)
                time.sleep(0.1)
                sys.exit(0)

            reloader_cls = reloader_engines[self.cfg.reload_engine]
            self.reloader = reloader_cls(extra_files=self.cfg.reload_extra_files,
                                         callback=changed)
            self.reloader.start()

        self.load_wsgi()
        self.cfg.post_worker_init(self) 

        # Enter main run loop
        self.booted = True
        self.run()            #主循环
```

`init_process()`是`Work进程`的入口文件，**启动工作进程**调用的是该方法，官方建议所有的实现子类的重载方法应该调用父类的该方法，该方法主要做了以下几件事：
1. 设置进程的进程组信息；
2. 创建单进程管道，**Worker**是通过管道来存储导致中断的信号，不直接处理，先收集起来，在主循环中处理；
2. 获取要监听的文件描述符，并将描述符设置为不可被子进程继承；
3. 设置中断信号处理函数;
4. 设置代码更新时，自动重启的配置
5. **获取实现了wsgi协议的app对象**
6. 进入主循环方法

```
    def run(self):
        """\
        This is the mainloop of a worker process. You should override
        this method in a subclass to provide the intended behaviour
        for your particular evil schemes.
        """
        raise NotImplementedError()
```

`Workder`类没有实现`run()`，由子类去实现具体的逻辑。

再来看看`WorkerTmp `类。
####WorkerTmp

```
# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.

import os
import platform
import tempfile

from gunicorn import util

PLATFORM = platform.system()
IS_CYGWIN = PLATFORM.startswith('CYGWIN')

class WorkerTmp(object):

    def __init__(self, cfg):
        old_umask = os.umask(cfg.umask)
        fdir = cfg.worker_tmp_dir
        if fdir and not os.path.isdir(fdir):
            raise RuntimeError("%s doesn't exist. Can't create workertmp." % fdir)
        fd, name = tempfile.mkstemp(prefix="wgunicorn-", dir=fdir)

        # allows the process to write to the file
        util.chown(name, cfg.uid, cfg.gid)
        os.umask(old_umask)

        # unlink the file so we don't leak tempory files
        try:
            if not IS_CYGWIN:
                # 即使这里unlink了文件，已经打开了文件描述符仍然可以访问该文件内容  close能够实施删除文件内容的操作，必定因为在close之前有一个unlink操作。
                util.unlink(name)
            self._tmp = os.fdopen(fd, 'w+b', 1)
        except:
            os.close(fd)
            raise

        self.spinner = 0

    def notify(self):
        self.spinner = (self.spinner + 1) % 2
        os.fchmod(self._tmp.fileno(), self.spinner)         #  更新时间戳

    def last_update(self):
        return os.fstat(self._tmp.fileno()).st_ctime

    def fileno(self):
        return self._tmp.fileno()

    def close(self):
        return self._tmp.close()
```

`WorkTmp`类主要的作用是创建一个临时文件，子进程通过更新该文件的时间戳，父进程定期检查子进程临时文件的时间戳确定子进程是否存活。
`WorkTmp._init__()`在系统创建了临时文件并获取其文件描述符，然后`unlink`该文件，防止子进程关闭后没有删除文件，，即使被`unlink`了，已经打开的文件描述符仍然访问文件。
`WorkTmp.notify()`通过更改文件的权限来更新文件修改时间。
`WorkTmp.last_update()`用来获取文件最后一次更新的时间。

最后看下工作进程的一个实现子类`ThreadWorker`。

#### ThreadWorker
>该类实现了父类的`Woker.run()`方法，并重载了部分其他方法。

```python
 def init_process(self):
        """初始化函数
        """
        self.tpool = futures.ThreadPoolExecutor(max_workers=self.cfg.threads)
        self.poller = selectors.DefaultSelector()       # 利用系统提供的selector
        self._lock = RLock()                            # 创建可重入锁
        super(ThreadWorker, self).init_process()
```

初始化函数做了以下事情：
1. 通过`concurrent.futures.ThreadPoolExecutor`创建线程池，线程的数量由配置文件的`thread`决定；
2. 通过`selectors.DefaultSelector()`获取符合所在平台的最优的I/O复用，如`Linux`使用`epoll`，`Mac`下面使用`Kqueue`，这个模块隐藏了底层的平台细节，对外提供统一的接口；
3. 创建一个可重入锁；
4. 调用父类的`init_process()`，在该方法里面调用了`run()`方法。

```
    def run(self):
        """运行的主函数
            ①通知父进程，我还活着
            ②监听事件
            ③处理监听事件
            ④判断父进程是否已经挂了，是的话退出循环
            ⑤murder 超过keep-alive最长的时间的请求
        """

        # init listeners, add them to the event loop
        for sock in self.sockets:
            sock.setblocking(False)                                             # 设置为非阻塞
            # a race condition during graceful shutdown may make the listener
            # name unavailable in the request handler so capture it once here
            server = sock.getsockname()
            acceptor = partial(self.accept, server)  # self.acceptor的偏函数
            self.poller.register(sock, selectors.EVENT_READ, acceptor)          #register(fileobj, events, data=None) 用data来保存callback函数

        while self.alive:                                                       # 主循环
            # notify the arbiter we are alive
            self.notify()                                                       # todo 通知机制？

            # can we accept more connections?
            if self.nr_conns < self.worker_connections:                         # 防止超过并发数
                # wait for an event
                # selector新写法
                events = self.poller.select(1.0)                                # 等待事件
                for key, _ in events:
                    callback = key.data                                         #callback从data获取
                    callback(key.fileobj)

                # check (but do not wait) for finished requests
                result = futures.wait(self.futures, timeout=0,
                        return_when=futures.FIRST_COMPLETED)                    #等待队列事件 futures.wait 接收的第一个参数是一个可迭代对象，无阻塞等待完成
            else:
                # wait for a request to finish
                result = futures.wait(self.futures, timeout=1.0,                # 阻塞等待
                        return_when=futures.FIRST_COMPLETED)

            # clean up finished requests
            for fut in result.done:
                self.futures.remove(fut)

            if not self.is_parent_alive(): # 通过判断ppid是否已经发生变化
                break

            # hanle keepalive timeouts
            self.murder_keepalived()

        self.tpool.shutdown(False)
        self.poller.close()

        for s in self.sockets:
            s.close()

        futures.wait(self.futures, timeout=self.cfg.graceful_timeout)       # 优雅关闭等待的最长时间
```

`run()`方法中主要做了以下事情：
1. 更新`tmpfile`时间戳
1. 获取就绪的请求连接；
2. 如果并发数允许，分配一个线程处理请求；
3. 判断父进程是否已经停止工作，有的话准备退出主循环；
4. 杀死已经允许最大连接事件的`keep-alive`连接。

下面是一个请求刚进来的处理过程：
```
    def _wrap_future(self, fs, conn):
        """将futuren放入队列中，并设置处理完成后的回调函数
        
        Arguments:
            fs {[type]} -- [description]
            conn {[type]} -- [description]
        """

        fs.conn = conn
        self.futures.append(fs)
        fs.add_done_callback(self.finish_request)

    def enqueue_req(self, conn):
        """将请求放入线程处理
        
        Arguments:
            conn {[type]} -- [description]
        """

        conn.init()
        # submit the connection to a worker
        fs = self.tpool.submit(self.handle, conn)
        self._wrap_future(fs, conn)

    def accept(self, server, listener):
        """监听时间处理函数
        
        Arguments:
            server {[type]} -- [description]
            listener {[type]} -- [description]
        """

        try:
            sock, client = listener.accept()
            # initialize the connection object
            conn = TConn(self.cfg, sock, client, server)
            self.nr_conns += 1                                      # 增加当前正在处理的请求数
            # enqueue the job
            self.enqueue_req(conn)
        except EnvironmentError as e:
            if e.errno not in (errno.EAGAIN,
                    errno.ECONNABORTED, errno.EWOULDBLOCK):
                raise
```

1. 从`socket`中`accept`返回一个与客户端连接的socket；
2. 将`socket`作为`self.handler()`方法的参数启动线程；
3. 注册线程运行完成后的回调函数。

`self.handler()`主要的部分在于其调用的`self.handle_request()`，因此直接看`self.handle_request()`做了哪些事情：

```
    def handle_request(self, req, conn):
        """主要的处理函数
        """

        environ = {}
        resp = None
        try:
            self.cfg.pre_request(self, req)
            request_start = datetime.now()
            resp, environ = wsgi.create(req, conn.sock, conn.client,
                    conn.server, self.cfg)
            environ["wsgi.multithread"] = True
            self.nr += 1
            if self.alive and self.nr >= self.max_requests:
                self.log.info("Autorestarting worker after current request.")
                resp.force_close()
                self.alive = False

            if not self.cfg.keepalive:
                resp.force_close()
            elif len(self._keep) >= self.max_keepalived:
                resp.force_close()

            respiter = self.wsgi(environ, resp.start_response)
            try:
                if isinstance(respiter, environ['wsgi.file_wrapper']):
                    resp.write_file(respiter)
                else:
                    for item in respiter:
                        resp.write(item)

                resp.close()
                request_time = datetime.now() - request_start
                self.log.access(resp, req, environ, request_time)
            finally:
                if hasattr(respiter, "close"):
                    respiter.close()

            if resp.should_close():
                self.log.debug("Closing connection.")
                return False
        except EnvironmentError:
            # pass to next try-except level
            util.reraise(*sys.exc_info())
        except Exception:
            if resp and resp.headers_sent:
                # If the requests have already been sent, we should close the
                # connection to indicate the error.
                self.log.exception("Error handling request")
                try:
                    conn.sock.shutdown(socket.SHUT_RDWR)
                    conn.sock.close()
                except EnvironmentError:
                    pass
                raise StopIteration()
            raise
        finally:
            try:
                self.cfg.post_request(self, req, environ, resp)
            except Exception:
                self.log.exception("Exception in post_request hook")

        return True
```

除了一些配置和环境相关的处理，关键的在于`respiter = self.wsgi(environ, resp.start_response)`这行代码，这行代码获取了实现`wsgi`协议的`app`并运行，将获取后的结果返回给客户端。
**这里就是整个请求处理的关键，只要符合wsgi协议的框架，都可以这样接入Gunicorn**。

整个`ThreadWork`的处理流程，如下图：

![Gunicorn.ThreadWorker](https://upload-images.jianshu.io/upload_images/6201701-930f7f15c6df3c9b.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)
