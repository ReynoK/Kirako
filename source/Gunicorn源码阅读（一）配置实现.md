Title: Gunicorn源码阅读（一）配置实现 
Date: 2018-10-14 21:11:34
Category: 技术 
Tag: python
============================================================
>最近使用Gunicorn+Flask部署了一套服务，顺便研究下Gunicorn的源码，看看Python 的Prefork模型是如何实现的。具体Gunicorn的用法可以看[官方文档]()，本文直接从源码开始入手。

官方主页：[Gunicorn](https://gunicorn.org)
官方文档：[Gunicorn Document](http://docs.gunicorn.org/en/stable/)
源码版本：gunicorn (version 19.9.0)
<!--more-->
源码目录结构：

```
gunicorn/
├── __init__.py
├── _compat.py
├── app
│   ├── __init__.py
│   ├── base.py
│   ├── pasterapp.py
│   └── wsgiapp.py
├── arbiter.py
├── config.py
├── debug.py
├── errors.py
├── glogging.py
├── http
│   ├── __init__.py
│   ├── body.py
│   ├── errors.py
│   ├── message.py
│   ├── parser.py
│   ├── unreader.py
│   └── wsgi.py
├── instrument
│   ├── __init__.py
│   └── statsd.py
├── pidfile.py
├── reloader.py
├── sock.py
├── systemd.py
├── util.py
└── workers
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

主要分为4部分
1. app
2. config
3. arbiter
4. worker

先从生成配置项的`config.py`开始。

>config.py文件主要是用生成配置对象cfg，为每一个配置项生成一个对象。


```python
class Setting(object):
    name = None
    value = None
    section = None
    cli = None
    validator = None
    type = None
    meta = None
    action = None
    default = None
    short = None
    desc = None
    nargs = None
    const = None

    def __init__(self):
        if self.default is not None:
            self.set(self.default)

    def add_option(self, parser):
        if not self.cli:
            return
        args = tuple(self.cli)

        help_txt = "%s [%s]" % (self.short, self.default)
        help_txt = help_txt.replace("%", "%%")

        kwargs = {
            "dest": self.name,
            "action": self.action or "store",
            "type": self.type or str,
            "default": None,
            "help": help_txt
        }

        if self.meta is not None:
            kwargs['metavar'] = self.meta

        if kwargs["action"] != "store":
            kwargs.pop("type")

        if self.nargs is not None:
            kwargs["nargs"] = self.nargs

        if self.const is not None:
            kwargs["const"] = self.const

        parser.add_argument(*args, **kwargs)

    def copy(self):
        return copy.copy(self)

    def get(self):
        return self.value

    def set(self, val):
        if not callable(self.validator):
            raise TypeError('Invalid validator: %s' % self.name)
        self.value = self.validator(val)

    def __lt__(self, other):
        return (self.section == other.section and
                self.order < other.order)
    __cmp__ = __lt__

Setting = SettingMeta('Setting', (Setting,), {})
```

首先看`Setting`这个类，其中主要定义了模块`ArgumentParser`解析命令行参数需要的信息，其他如属性`value`是解析出来的值，属性`validator`是检查函数。（文件中定义了许多以`validate_`开头的函数，用来针对不同的配置项，不再赘述）
`Setting = SettingMeta('Setting', (Setting,), {})`将`Setting`的元类设置为`SettingMeta`，**表明`Setting`这个类及其子类都是由`SettingMeta`创建出来的**。
再来看看`SettingMeta`。

```python
KNOWN_SETTINGS = []

class SettingMeta(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(SettingMeta, cls).__new__
        parents = [b for b in bases if isinstance(b, SettingMeta)]
        if not parents:
            return super_new(cls, name, bases, attrs)

        attrs["order"] = len(KNOWN_SETTINGS)
        attrs["validator"] = staticmethod(attrs["validator"])

        new_class = super_new(cls, name, bases, attrs)
        new_class.fmt_desc(attrs.get("desc", ""))
        KNOWN_SETTINGS.append(new_class)
        return new_class

    def fmt_desc(cls, desc):
        desc = textwrap.dedent(desc).strip()
        setattr(cls, "desc", desc)
        setattr(cls, "short", desc.splitlines()[0])
```

文件定义了`KNOWN_SETTINGS `列表，每个继承`Setting`的类（`Setting`本身除外）都会被添加到该属性，并且该元类还做了额外的工作，如为每个配置生成序号，将每个`validator`设置为**static方法**。

看下其中的一个配置类`Bind`：

```python
class Bind(Setting):
    name = "bind"
    action = "append"
    section = "Server Socket"
    cli = ["-b", "--bind"]
    meta = "ADDRESS"
    validator = validate_list_string

    if 'PORT' in os.environ:
        default = ['0.0.0.0:{0}'.format(os.environ.get('PORT'))]
    else:
        default = ['127.0.0.1:8000']

    desc = """\
        The socket to bind.

        A string of the form: ``HOST``, ``HOST:PORT``, ``unix:PATH``. An IP is
        a valid ``HOST``.

        Multiple addresses can be bound. ex.::

            $ gunicorn -b 127.0.0.1:8000 -b [::1]:8000 test:app

        will bind the `test:app` application on localhost both on ipv6
        and ipv4 interfaces.
        """
```

每一个配置类都像上面这样的形式定义，十分简洁。

```python
def make_settings(ignore=None):
    settings = {}
    ignore = ignore or ()
    for s in KNOWN_SETTINGS:
        setting = s()
        if setting.name in ignore:
            continue
        settings[setting.name] = setting.copy()
    return settings
```

`make_setting`方法会将所有定义的`Setting`子类实例化。

```python
class Config(object):

    def __init__(self, usage=None, prog=None):
        self.settings = make_settings()
        self.usage = usage
        self.prog = prog or os.path.basename(sys.argv[0])
        self.env_orig = os.environ.copy()

    def __getattr__(self, name):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %s" % name)
        return self.settings[name].get()

    def __setattr__(self, name, value):
        if name != "settings" and name in self.settings:
            raise AttributeError("Invalid access!")
        super(Config, self).__setattr__(name, value)

    def set(self, name, value):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %s" % name)
        self.settings[name].set(value)

    def get_cmd_args_from_env(self):
        if 'GUNICORN_CMD_ARGS' in self.env_orig:
            return shlex.split(self.env_orig['GUNICORN_CMD_ARGS'])
        return []

    def parser(self):
        kwargs = {
            "usage": self.usage,
            "prog": self.prog
        }
        parser = argparse.ArgumentParser(**kwargs)
        parser.add_argument("-v", "--version",
                action="version", default=argparse.SUPPRESS,
                version="%(prog)s (version " + __version__ + ")\n",
                help="show program's version number and exit")
        parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)

        keys = sorted(self.settings, key=self.settings.__getitem__)
        for k in keys:
            self.settings[k].add_option(parser)

        return parser

    @property
    def worker_class_str(self):
        """工作进行使用的模式
        
        Returns:
            [type] -- [description]
        """

        uri = self.settings['worker_class'].get()       

        ## are we using a threaded worker?
        is_sync = uri.endswith('SyncWorker') or uri == 'sync'
        if is_sync and self.threads > 1:
            return "threads"            # 如果定义的threads配置大于1，将使用 gthread模式
        return uri

    @property
    def worker_class(self):
        """工作进行使用的模式
        
        Returns:
            [type] -- [description]
        """

        uri = self.settings['worker_class'].get()

        ## are we using a threaded worker?
        is_sync = uri.endswith('SyncWorker') or uri == 'sync'
        if is_sync and self.threads > 1:
            uri = "gunicorn.workers.gthread.ThreadWorker"

        worker_class = util.load_class(uri)
        if hasattr(worker_class, "setup"):
            worker_class.setup()
        return worker_class

    @property
    def address(self):
        s = self.settings['bind'].get()
        return [util.parse_address(util.bytes_to_str(bind)) for bind in s]

    @property
    def uid(self):
        return self.settings['user'].get()

    @property
    def gid(self):
        return self.settings['group'].get()

    @property
    def proc_name(self):
        pn = self.settings['proc_name'].get()
        if pn is not None:
            return pn
        else:
            return self.settings['default_proc_name'].get()

    @property
    def logger_class(self):
        """日志类
        
        Returns:
            [type] -- [description]
        """

        uri = self.settings['logger_class'].get()
        if uri == "simple":
            # support the default
            uri = LoggerClass.default

        # if default logger is in use, and statsd is on, automagically switch
        # to the statsd logger
        if uri == LoggerClass.default:
            if 'statsd_host' in self.settings and self.settings['statsd_host'].value is not None:
                uri = "gunicorn.instrument.statsd.Statsd"

        logger_class = util.load_class(
            uri,
            default="gunicorn.glogging.Logger",
            section="gunicorn.loggers")

        if hasattr(logger_class, "install"):
            logger_class.install()
        return logger_class

    @property
    def is_ssl(self):
        return self.certfile or self.keyfile

    @property
    def ssl_options(self):
        opts = {}
        for name, value in self.settings.items():
            if value.section == 'SSL':
                opts[name] = value.get()
        return opts

    @property
    def env(self):
        raw_env = self.settings['raw_env'].get()
        env = {}

        if not raw_env:
            return env

        for e in raw_env:
            s = util.bytes_to_str(e)
            try:
                k, v = s.split('=', 1)
            except ValueError:
                raise RuntimeError("environment setting %r invalid" % s)

            env[k] = v

        return env

    @property
    def sendfile(self):
        if self.settings['sendfile'].get() is not None:
            return False

        if 'SENDFILE' in os.environ:
            sendfile = os.environ['SENDFILE'].lower()
            return sendfile in ['y', '1', 'yes', 'true']

        return True

    @property
    def reuse_port(self):
        return self.settings['reuse_port'].get()

    @property
    def paste_global_conf(self):
        raw_global_conf = self.settings['raw_paste_global_conf'].get()
        if raw_global_conf is None:
            return None

        global_conf = {}
        for e in raw_global_conf:
            s = util.bytes_to_str(e)
            try:
                k, v = re.split(r'(?<!\\)=', s, 1)
            except ValueError:
                raise RuntimeError("environment setting %r invalid" % s)
            k = k.replace('\\=', '=')
            v = v.replace('\\=', '=')
            global_conf[k] = v

        return global_conf
```

**`Config`对象使用了代理模式，用来控制对每个配置项的访问，访问`Config`对象的属性大部分会代理到对应的`Setting`子类对象。**
`Config. parser()`函数会返回一个`argparse.ArgumentParser`对象，用来解析命令行参数。

UML图：
![gunicorn.config](https://upload-images.jianshu.io/upload_images/6201701-c9905cc9b0fdb8bf.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)


