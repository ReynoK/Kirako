Title: Dockerfile使用笔记
Date: 2018-10-28 21:18:39
Category: 技术
Tag: Docker Linux
============================================================

> 最近在做项目时，从头搭了个基于Flask的小框架，由于小伙伴之前没有用Flaks写过项目，而我又引入了一些第三方包，为了方便小伙伴进行开发，无需重新自己从头搭建一套环境，就打算用Docker搭个环境，这样对大家都方便。之前学过Dockfile，不过忘记了大部分细节，因此，用这篇博客来记录。不过，用到啥，记啥，不想面面俱到，因此本篇随时更新。
<!--more-->

下面是我写的一个搭建`Flask`环境的`Dockerfile`文件

```dockerfile
FROM python:3.7.1-slim-stretch

RUN mv /etc/apt/sources.list /etc/apt/sources.list.bak  
COPY sources.list /etc/apt/sources.list
COPY requirements.txt /root/requirements.txt

RUN mkdir ~/.pip \
    && echo "[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple/" > ~/.pip/pip.conf \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai  /etc/localtime \
    && apt-get update \
    && apt-get install -y apt-utils \
    && apt-get install -y wget \
    && apt-get install -y curl \
    && apt-get install -y git \
    && apt-get install -y zsh \
    && chsh -s /bin/zsh \
    && pip install -r /root/requirements.txt

RUN sh -c "$(wget https://raw.github.com/robbyrussell/oh-my-zsh/master/tools/install.sh -O -)"  || true; \    
    echo "PROMPT='\$fg_bold[blue]%}(docker)\${ret_status} %{\$fg[cyan]%}%c%{\$reset_color%} \$(git_prompt_info)'" >> /root/.zshrc
ENV FLASK_ENV dev
ENV FLASK_APP main.py
ENV APP_DIR /code
WORKDIR /code/Vote

EXPOSE 5000     

CMD ["zsh"]
```

##### 基础指令介绍
######FROM
>FROM name:tag

指定用来制作镜像的基础镜像，从官网[hub](https://hub.docker.com/explore/)上面可以找到许多十分优质的镜像，你可以在其基础上进行修改。
我常用的基础镜像有`ubuntu`/`python`。
Docker还提供了一种虚拟镜像`scratch`，又表示空镜像，即不以任何系统为基础，这个用到的时候再详说把。

###### COPY
>COPY 原路径 ... 目标路径
COPY ["源路径", ... , "目标路径"] ---- 推荐

COPY只能复制build过程中上下文的文件，**上下文之外的文件不可复制**，一般Dockerfile文件所在的目录就是其上下文。

###### WORKDIR
>WORKDIR 工作目录路径

指定后续各层的工作路径，如果不存在，Docker为自动为你创建给目录。
**在RUN中`cd`并不会影响后续各层的工作目录，只会影响盖层当前处理的目录**。

###### EXPOSE
>EXPOSE <port1> ... <portn>

仅仅用于**声明**容器想要暴露的端口，实际开启的端口**由容器的服务决定**，**另一方面在随机端口映射时，Docker会随机映射Docker指定的端口**。

###### ENV
> ENV <key> <value>
ENV <key>=<value> <key2>=<value2> ...

设置环境变量，**后续的指令(用`$`访问)或者运行的容器均可以像普通环境变量一样使用变量**。

###### CMD
> CMD <命令>
CMD ["可执行文件","参数1","参数2"...]

设定容器启动时的**默认执行**命令，**该命令应该是可以在前台一直运行的进程，否则容器一启动完进程运行结束后就立马关闭了**。

###### RUN
> RUN <命令>
RUN ["可执行文件","参数1","参数2" ... ]

用来执行系统命令，如安装工具、解压包、下载文件等，主要构建镜像的逻辑都在于此。**因为在Docker中，每一个指令都会构建一层，因此尽量将命令都放在一个RUN指令中，用 `&&` 来串联**。
在命令最后需要**添加清理工作的命令**，如`apt-get purge -y --auto-remove wget`、`rm -rf /redis-3.2.5`等删除下载数据或文件的命令，防止这些无用数据被添加到镜像中。

###### 其他
1. 要使用`$`，需要使用`\`进行转义；
2. Dockerfile支持shell的换行`\`；
3. 使用`ln -sf /usr/share/zoneinfo/Asia/Shanghai  /etc/localtime`修改镜像的时区；

##### Docker-compose
>docker-compose本身使用来快速部署容器集群，它允许用户通过一个yml文件定义一组相关联的容器，从而成为一个项目。而我用compose的原因是方便自己定义启动容器的参数，从而无需在命令行中写入超长的命令启动，如`docker run --rm -it -v ~/.SpaceVim:/root/.SpaceVim -v ~/.SpaceVim.d:/root/.SpaceVim.d -v ~/.vimrc:/root/.vimrc -v ~/.config:/root/.config  develop`

通过`docker-compose`，我只需定义以下`yml`文件：

```yaml
version: '3'
services:
    develop:
        image: "develop:1.0"
        ports:
            - "5000:5000"
        command: "zsh"
        volumes: 
            - ~/.SpaceVim:/root/.SpaceVim
            - ~/.SpaceVim.d:/root/.SpaceVim.d
    terminal:
        image: "terminal:1.0"
        command: "zsh"
        volumes: 
            - ~/.SpaceVim:/root/.SpaceVim
            - ~/.SpaceVim.d:/root/.SpaceVim.d
```
就可以方便的使用命令`docker-compose run --rm image_name`启动我想要的容器，顺便也学习下`docker-compose`的用法。

###### 安装
`docker-compose`是`python`写的，因此通过`pip install docker-compose`就可以安装。

###### yml文件
>简单介绍我用过的

| key | value |
| :-:| :-:|
| version| docker-compose版本|
| image | 对应的镜像|
|ports | 端口映射|
|command|容器启动执行命令|
|volumes|卷映射|

###### docker-compose命令
>docker-compose [-f <arg>...] [options] [COMMAND] [ARGS...]

| Command | Description |
| :-:| :-:|
| config | 验证yml是否正确|
| exec | 进入指定的容器 |
| run |在指定服务器上执行一个命令，可带--rm参数，关闭后删除容器|
| up | 自动构建镜像，创建服务，启动服务等一条龙服务 |