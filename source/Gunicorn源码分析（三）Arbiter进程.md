Title: Gunicorn源码分析（三）Arbiter进程
Date: 2018-10-22 23:15:14
Category: 技术
Tag: python
============================================================
Write start here....>Worker进程专门用来负责处理请求，那么当Worker进程挂掉或需要重新启动又或者需要关闭时，又要怎么办呢？这时候就需要一个负责全局统筹的进程——Master进程，同时也是Gunicorn的核心。

Master进程主要在`arbiter.py`中`Arbiter `类实现，`arbiter`的意思是`仲裁者；裁决人`，也十分符合这个类的功能。

<!--more-->

```python
class Arbiter(object):
    def __init__(self, app):
    def _get_num_workers(self):
    def _set_num_workers(self, value):
    def setup(self, app):
    def start(self):
    def init_signals(self):
    def signal(self, sig, frame):
    def run(self):
    def handle_chld(self, sig, frame):
    def handle_hup(self):
    def handle_term(self):
    def handle_int(self):
    def handle_quit(self):
    def handle_ttin(self):
    def handle_ttou(self):
    def handle_usr1(self):
    def handle_usr2(self):
    def handle_winch(self):
    def maybe_promote_master(self):
    def wakeup(self):
    def halt(self, reason=None, exit_status=0):
    def sleep(self):
    def stop(self, graceful=True):
    def reexec(self):
    def reload(self):
    def murder_workers(self): # 杀死tmpfile不更新的子进程
    def reap_workers(self):    # 捕获子进程结束信号
    def manage_workers(self):
    def spawn_worker(self):
    def spawn_workers(self):  # 产生work进程，实际由spawn_worker生成子进程
    def kill_workers(self, sig): 
    def kill_worker(self, pid, sig):  # 通过信号控制进程
```
可以从方法名称看出，`Arbiter`由以下部分组成：
1. 初始化；
2. 信号处理函数；
3. 子进程管理（包括重启、杀死、启动工作进程）；
4. 主进程管理。

##### 初始化
----

```
# I love dynamic languages
    SIG_QUEUE = []
    SIGNALS = [getattr(signal, "SIG%s" % x)
               for x in "HUP QUIT INT TERM TTIN TTOU USR1 USR2 WINCH".split()]
    # {1: 'hup', 2: 'int', 3: 'quit', 4: 'ill', 5: 'trap', 6: 'iot', 7: 'emt', 8: 'fpe', 9: 'kill', 10: 'bus', 11: 'segv', 12: 'sys', 13: 'pipe', 14: 'alrm', 15: 'term', 16: 'urg', 17: 'stop', 18: 'tstp', 19: 'cont', 20: 'chld', 21: 'ttin', 22: 'ttou', 23: 'io', 24: 'xcpu', 25: 'xfsz', 26: 'vtalrm', 27: 'prof', 28: 'winch', 29: 'info', 30: 'usr1', 31: 'usr2'}
    SIG_NAMES = dict(
        (getattr(signal, name), name[3:].lower()) for name in dir(signal)
        if name[:3] == "SIG" and name[3] != "_"
    )

    def __init__(self, app):
        """构造函数
        会调用 setup()函数
        Arguments:
            app {[type]} -- [description]
        """

        os.environ["SERVER_SOFTWARE"] = SERVER_SOFTWARE

        self._num_workers = None
        self._last_logged_active_worker_count = None
        self.log = None

        self.setup(app)

        self.pidfile = None
        self.systemd = False
        self.worker_age = 0
        self.reexec_pid = 0
        self.master_pid = 0
        self.master_name = "Master"

        cwd = util.getcwd()

        args = sys.argv[:]
        args.insert(0, sys.executable)

        # init start context
        # 设置启动命令，重启用
        self.START_CTX = {
            "args": args,
            "cwd": cwd,
            0: sys.executable
        }

    def setup(self, app):
        """配置函数，构造函数调用
        
        Arguments:
            app {[type]} -- [description]
        """

        self.app = app
        self.cfg = app.cfg

        if self.log is None:
            self.log = self.cfg.logger_class(app.cfg)

        # reopen files
        if 'GUNICORN_FD' in os.environ:
            self.log.reopen_files()

        self.worker_class = self.cfg.worker_class
        self.address = self.cfg.address
        self.num_workers = self.cfg.workers
        self.timeout = self.cfg.timeout
        self.proc_name = self.cfg.proc_name     #进程命名

        self.log.debug('Current configuration:\n{0}'.format(
            '\n'.join(
                '  {0}: {1}'.format(config, value.value)
                for config, value
                in sorted(self.cfg.settings.items(),
                          key=lambda setting: setting[1]))))

        # set enviroment' variables
        if self.cfg.env:
            for k, v in self.cfg.env.items():
                os.environ[k] = v
        # 预重载应用
        if self.cfg.preload_app:
            self.app.wsgi()
```

初始化十分简单，无非就是初始一些变量，然后从配置`cfg`中读取配置，设置Worker进程的实现形式、最高并发数等等x。

##### 信号处理
----
`Arbiter`支持以下信号：

| 信号 | 功能 |  |
| :-: | :-: | :-: |
|  QUIT/INT   | 关闭进程    |  `stop()`    |
|  CLD | 捕获僵死子进程 | `reap_workers()`|
|  HUP |重新导入配置，并逐步重启子进程|`reload()`|
| TERM | 优雅关闭Gunicorn | -|
| TTIN| 手工增加工作子进程 | `manage_workers()`|
|TTOU| 手工减少工作子进程 | `manage_workers()` |
|USR1 | 日志相关，重启日志文件 |`kill_workers()`|
|USR2| 在线升级Gunicorn，旧进程需要手动kill|`reexec()`|
|WINCH|主进程Dameon模式下，优雅的关闭工作进程| `kill_workers()`|

```
    def init_signals(self):
        """初始化信号处理函数
        Initialize master signal handling. Most of the signals
        are queued. Child signals only wake up the master.
        """
        # close old PIPE
        for p in self.PIPE:
            os.close(p)

        # initialize the pipe
        self.PIPE = pair = os.pipe()
        for p in pair:
            util.set_non_blocking(p)
            util.close_on_exec(p)

        self.log.close_on_exec()

        # initialize all signals
        for s in self.SIGNALS:
            signal.signal(s, self.signal)
        signal.signal(signal.SIGCHLD, self.handle_chld)

    def signal(self, sig, frame):
        """通过队列去捕捉信号，而不是直接执行
        Arguments:
            sig {[type]} -- [description]
            frame {[type]} -- [description]
        """

        if len(self.SIG_QUEUE) < 5:
            self.SIG_QUEUE.append(sig)
            self.wakeup()

    def wakeup(self):
        """
        Wake up the arbiter by writing to the PIPE
        """
        try:
            os.write(self.PIPE[1], b'.')
        except IOError as e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise

    def sleep(self):
        """\
        Sleep until PIPE is readable or we timeout.
        A readable PIPE means a signal occurred.
        """
        try:
            ready = select.select([self.PIPE[0]], [], [], 1.0)
            if not ready[0]:
                return
            while os.read(self.PIPE[0], 1):
                pass
        except (select.error, OSError) as e:
            # TODO: select.error is a subclass of OSError since Python 3.3.
            error_number = getattr(e, 'errno', e.args[0])
            if error_number not in [errno.EAGAIN, errno.EINTR]:
                raise
        except KeyboardInterrupt:
            sys.exit()
```

主进程`Arbiter`对信号处理比较特殊，对于每个捕获的信号，它不进行直接处理，而是创建了一个队列，专门用来放置信号，**这样无论在何处产生的信号（在信号处理中又产生了信号，亦或者在生成工作进程的时候等等），都会被放置到队列中（队列最多只能存放4个信号），而专门的信号处理在后面可以看到，在`run()`方法中统一处理。**
这里使用了一个小技巧，每次放置信号到队列中的时候同时会调用`wakeup`方法，该方法会向之前创建的管道中写入数据，这样在主进程在`sleep`(实际是阻塞在`select`)的时候可以及时检测之前有信号没有处理，从而退出`sleep`。

##### Worker进程的生成
---

```python
    def spawn_worker(self):
        """产生子进程
        
        Returns:
            [type] -- [description]
        """

        self.worker_age += 1
        worker = self.worker_class(self.worker_age, self.pid, self.LISTENERS,
                                   self.app, self.timeout / 2.0,
                                   self.cfg, self.log)
        self.cfg.pre_fork(self, worker)
        pid = os.fork()                         # 创建子进程
        if pid != 0:
            worker.pid = pid
            self.WORKERS[pid] = worker
            return pid

        # Do not inherit the temporary files of other workers               # 关闭其他工作进程的tmpfile文件
        for sibling in self.WORKERS.values():
            sibling.tmp.close()

        # Process Child
        worker.pid = os.getpid()
        try:
            util._setproctitle("worker [%s]" % self.proc_name)
            self.log.info("Booting worker with pid: %s", worker.pid)
            self.cfg.post_fork(self, worker)
            worker.init_process()                                       # 这里会run子进程
            sys.exit(0)
        except SystemExit:
            raise
        except AppImportError as e:
            self.log.debug("Exception while loading the application",
                           exc_info=True)
            print("%s" % e, file=sys.stderr)
            sys.stderr.flush()
            sys.exit(self.APP_LOAD_ERROR)
        except:
            self.log.exception("Exception in worker process")
            if not worker.booted:
                sys.exit(self.WORKER_BOOT_ERROR)
            sys.exit(-1)
        finally:
            self.log.info("Worker exiting (pid: %s)", worker.pid)
            try:
                worker.tmp.close()                                     # 关闭临时文件
                self.cfg.worker_exit(self, worker)
            except:
                self.log.warning("Exception during worker exit:\n%s",
                                  traceback.format_exc())

    def spawn_workers(self):
        """\
        产生work进程
        Spawn new workers as needed.

        This is where a worker process leaves the main loop
        of the master process.
        """

        for _ in range(self.num_workers - len(self.WORKERS)):               #数量由当前工作进程和目标工作进程之间的数量决定
            self.spawn_worker()
            time.sleep(0.1 * random.random())
```
启用新的`Worker`进程只会在`Worker数量小于指定数量`或者重新导入配置文件时调用。`Arbiter`通过`os.fork()`创建`Worker`进程，在`Worker`创建好之后，由于继承了父进程打开的文件描述符，其中包含了其他`Worker`进程的`tmpfile`文件，需要将其关闭（避免耗费资源），然后就可以进入`Worker.init_process()`中，开始处理请求。

##### Worker进程的毁灭
----

```
    def kill_workers(self, sig):
        """\
        Kill all workers with the signal `sig`
        :attr sig: `signal.SIG*` value
        """
        worker_pids = list(self.WORKERS.keys())
        for pid in worker_pids:
            self.kill_worker(pid, sig)

    def kill_worker(self, pid, sig):
        """\
        通过信号通知子进程关闭
        Kill a worker

        :attr pid: int, worker pid
        :attr sig: `signal.SIG*` value
         """
        try:
            os.kill(pid, sig)
        except OSError as e:
            if e.errno == errno.ESRCH:
                try:
                    worker = self.WORKERS.pop(pid)              # 第一次杀死并不会从workers中删除，只有杀死成功后，第二次会抛出进程不存在的异常，这时候才从workders中删除
                    worker.tmp.close()
                    self.cfg.worker_exit(self, worker)
                    return
                except (KeyError, OSError):
                    return
            raise
    def murder_workers(self):
        """\
        杀死无用的工作进程，通过检测 tmpfile的时间戳
        Kill unused/idle workers
        """
        if not self.timeout:
            return
        workers = list(self.WORKERS.items())
        for (pid, worker) in workers:
            try:
                if time.time() - worker.tmp.last_update() <= self.timeout:
                    continue
            except (OSError, ValueError):
                continue

            if not worker.aborted:
                self.log.critical("WORKER TIMEOUT (pid:%s)", pid)
                worker.aborted = True
                self.kill_worker(pid, signal.SIGABRT)
            else:
                self.kill_worker(pid, signal.SIGKILL)
```

Worker进程的关闭主要是通过由`Arbiter`主进程对其发送`signal`来操作，主要有以下场景：
1. 通过检查`Worker`进程对应的`tmpfile`发现其出现问题；
2. `Arbiter`进程接受到信号需要关闭或重启；
3. `Worker`进程数量大于指定数量。

##### Arbiter的热更新与重启
---

```
   def reexec(self):
        """\
        重新创建一个主进程和工作进程
        Relaunch the master and workers.
        """
        if self.reexec_pid != 0:
            self.log.warning("USR2 signal ignored. Child exists.")
            return

        if self.master_pid != 0:
            self.log.warning("USR2 signal ignored. Parent exists.")
            return

        master_pid = os.getpid()
        self.reexec_pid = os.fork()
        if self.reexec_pid != 0:
            return

        self.cfg.pre_exec(self)

        environ = self.cfg.env_orig.copy()
        environ['GUNICORN_PID'] = str(master_pid)

        if self.systemd:
            environ['LISTEN_PID'] = str(os.getpid())
            environ['LISTEN_FDS'] = str(len(self.LISTENERS))
        else:
            environ['GUNICORN_FD'] = ','.join(
                str(l.fileno()) for l in self.LISTENERS)

        os.chdir(self.START_CTX['cwd'])

        # exec the process using the original environment
        os.execvpe(self.START_CTX[0], self.START_CTX['args'], environ)

    def reload(self):
        """重新读取配置，热更新
        """

        old_address = self.cfg.address

        # reset old environment
        for k in self.cfg.env:
            if k in self.cfg.env_orig:
                # reset the key to the value it had before
                # we launched gunicorn
                os.environ[k] = self.cfg.env_orig[k]
            else:
                # delete the value set by gunicorn
                try:
                    del os.environ[k]
                except KeyError:
                    pass

        # reload conf
        self.app.reload()
        self.setup(self.app)

        # reopen log files
        self.log.reopen_files()

        # do we need to change listener ?
        if old_address != self.cfg.address:
            # close all listeners
            for l in self.LISTENERS:
                l.close()
            # init new listeners
            self.LISTENERS = sock.create_sockets(self.cfg, self.log)
            listeners_str = ",".join([str(l) for l in self.LISTENERS])
            self.log.info("Listening at: %s", listeners_str)

        # do some actions on reload
        self.cfg.on_reload(self)

        # unlink pidfile
        if self.pidfile is not None:
            self.pidfile.unlink()

        # create new pidfile
        if self.cfg.pidfile is not None:
            self.pidfile = Pidfile(self.cfg.pidfile)
            self.pidfile.create(self.pid)

        # set new proc_name
        util._setproctitle("master [%s]" % self.proc_name)

        # spawn new workers
        for _ in range(self.cfg.workers):
            self.spawn_worker()

        # manage workers
        self.manage_workers()
```

`Arbiter`提供2种方式'重启'，一种是热更新，不重启`Arbiter`，仅仅是重新读取配置，然后生成新的`Worker`进程，逐步关闭之前产生的`Worker`进程；另一种是，完全重启一个新的`Arbiter`进程（同时又是旧`Arbiter`的子进程），然后这个新的`Arbiter`又启动新的`Worker`进程，**旧的Arbiter需要手动杀死**。

##### Arbiter的主循环
---

```
    def start(self):
        """启动Arbiter
        """
        """\
        Initialize the arbiter. Start listening and set pidfile if needed.
        """
        self.log.info("Starting gunicorn %s", __version__)

        if 'GUNICORN_PID' in os.environ:
            self.master_pid = int(os.environ.get('GUNICORN_PID'))
            self.proc_name = self.proc_name + ".2"
            self.master_name = "Master.2"

        self.pid = os.getpid()
        if self.cfg.pidfile is not None:
            pidname = self.cfg.pidfile
            if self.master_pid != 0:
                pidname += ".2"
            self.pidfile = Pidfile(pidname)
            self.pidfile.create(self.pid)
        self.cfg.on_starting(self)

        self.init_signals()

        if not self.LISTENERS:
            fds = None
            listen_fds = systemd.listen_fds()
            if listen_fds:
                self.systemd = True
                fds = range(systemd.SD_LISTEN_FDS_START,
                            systemd.SD_LISTEN_FDS_START + listen_fds)

            elif self.master_pid:
                fds = []
                for fd in os.environ.pop('GUNICORN_FD').split(','):
                    fds.append(int(fd))

            self.LISTENERS = sock.create_sockets(self.cfg, self.log, fds)

        listeners_str = ",".join([str(l) for l in self.LISTENERS])
        self.log.debug("Arbiter booted")
        self.log.info("Listening at: %s (%s)", listeners_str, self.pid)
        self.log.info("Using worker: %s", self.cfg.worker_class_str)

        # check worker class requirements
        if hasattr(self.worker_class, "check_config"):
            self.worker_class.check_config(self.cfg, self.log)

        self.cfg.when_ready(self)

    def run(self):
        """Master进程主循环
        ① self.start()
        """

        "Main master loop."
        self.start()
        util._setproctitle("master [%s]" % self.proc_name)              # 设置进程名称

        try:
            self.manage_workers()

            while True:
                self.maybe_promote_master()
                # 在这里捕捉信号
                sig = self.SIG_QUEUE.pop(0) if self.SIG_QUEUE else None
                if sig is None:
                    self.sleep()
                    self.murder_workers()
                    self.manage_workers()
                    continue

                if sig not in self.SIG_NAMES:
                    self.log.info("Ignoring unknown signal: %s", sig)
                    continue

                signame = self.SIG_NAMES.get(sig)
                handler = getattr(self, "handle_%s" % signame, None)
                if not handler:
                    self.log.error("Unhandled signal: %s", signame)
                    continue
                self.log.info("Handling signal: %s", signame)
                handler()
                self.wakeup()
        except StopIteration:
            self.halt()
        except KeyboardInterrupt:
            self.halt()
        except HaltServer as inst:
            self.halt(reason=inst.reason, exit_status=inst.exit_status)
        except SystemExit:
            raise
        except Exception:
            self.log.info("Unhandled exception in main loop",
                          exc_info=True)
            self.stop(False)
            if self.pidfile is not None:
                self.pidfile.unlink()
            sys.exit(-1)

    def manage_workers(self):
        """\
        进程管理
        Maintain the number of workers by spawning or killing
        as required.
        """
        if len(self.WORKERS) < self.num_workers:
            self.spawn_workers()

        workers = self.WORKERS.items()
        workers = sorted(workers, key=lambda w: w[1].age)
        while len(workers) > self.num_workers:              # 如果进程数多于指定的进程数，则kill掉存货时间最长的work进程
            (pid, _) = workers.pop(0)
            self.kill_worker(pid, signal.SIGTERM)

        active_worker_count = len(workers)
        if self._last_logged_active_worker_count != active_worker_count:
            self._last_logged_active_worker_count = active_worker_count
            self.log.debug("{0} workers".format(active_worker_count),
                           extra={"metric": "gunicorn.workers",
                                  "value": active_worker_count,
                                  "mtype": "gauge"})
```

`run()`就是`Arbiter`进程的主逻辑部分，上层在启动主进程是，就是调用该方法，该方法通过调用上面讲的方法来'统筹全局'：
1. 设置运行时参数，包括进程名称、信号处理函数等；
2. 处理已被捕获的信号；
3. `Worker`进的管理（包括新增和杀死）。

以上就是整个`Arbiter`的构成。