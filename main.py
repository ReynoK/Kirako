import logging
import tornado.web
import tornado.ioloop
import tornado.options
import tornado.log
import os
import uuid
import mistune
import sqlite3
import math
import settings

from tornado.web import url, Application

main_dir = os.getcwd()
post_db = os.path.join(main_dir, "post.db")


def markdown_2_html(content):
    markdown = mistune.Markdown()
    return markdown(content)


class LogFormatter(tornado.log.LogFormatter):

    def __init__(self):
        log_id = str(uuid.uuid4())

        super(LogFormatter, self).__init__(
            fmt='%(color)s[%(levelname)s][%(asctime)s][{log_id}] [%(filename)s:%(funcName)s:%(lineno)d]%(end_color)s %(message)s'.format(
                log_id=log_id),
            datefmt='%Y-%m-%d %H:%M:%S'
        )

class BaseHandler(tornado.web.RequestHandler):
    def initialize(self):
        """sqlite3 的 cursor在这里初始化
        
        Arguments:
            tornado {[type]} -- [description]
        
        Returns:
            [type] -- [description]
        """

        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        self.conn = sqlite3.connect(post_db)
        self.conn.row_factory = dict_factory

        self.cursor = self.conn.cursor()

    def get_post_num(self):
        """获取日志数量
        
        Returns:
            [type] -- [description]
        """

        sql = "select count(*) as num from post"
        self.cursor.execute(sql)
        result = self.cursor.fetchone()
        
        return result['num']

    def get_tag_num(self):
        """获取标签数量
        
        Returns:
            [type] -- [description]
        """

        sql = "select distinct tag as num from tag"
        self.cursor.execute(sql)
        result = self.cursor.fetchall()

        return len(result)
    
    def get_category_num(self):
        """获取分类数量
        
        Returns:
            [type] -- [description]
        """

        sql = "select distinct category from post"
        self.cursor.execute(sql)
        result = self.cursor.fetchall()

        return len(result)

class NotFoundHandler(BaseHandler):
    def get(self):
        tornado.log.access_log.error("go into 404 not found")
        self.render("404.html")

    def post(self):
        tornado.log.access_log.info("go into 404 not found")
        self.render("404.html")


class PageHandler(BaseHandler):
    def get(self, page=1):
        page = int(page)
        page_num = 5
        sql = "select * from post order by created desc limit ?,?"
        self.cursor.execute(sql, ((page-1)*page_num, page_num))
        post_list = self.cursor.fetchall()

        sql = "select count(*) as total from post"
        self.cursor.execute(sql)
        page_info = self.cursor.fetchone()
        page_total =  math.ceil(float(page_info["total"])/page_num)

        for post in post_list:
            if post['description'] == '':
                post['description'] = "<p>╮(╯_╰)╭作者很懒，什么都没有写。</p>"

        self.render("index.html", post_list=post_list,
                    page_total=page_total, cur_page=page)

class IndexHandler(BaseHandler):
    def get(self):
        self.redirect(self.reverse_url('home'))

class AboutMeHandler(BaseHandler):
    def get(self):
        self.render("aboutme.html")


class ArchiveHandler(BaseHandler):
    """归档列表
    
    Arguments:
        BaseHandler {[type]} -- [description]
    """

    def get(self):

        sql = "select * from post order by created desc"
        self.cursor.execute(sql)
        archive_list = self.cursor.fetchall()

        if archive_list is None:
            archive_list = []
        self.render("archive.html",archive_list=archive_list)


class MenuUIModule(tornado.web.UIModule):
    def render(self):
        menu_list = [
            {"name": "首页", "url_name": "home"},
            {"name": "分类", "url_name": "categories"},
            {"name": "归档", "url_name": "archive"},
            {"name":"标签", "url_name":"tags"},
            # {"name":"友链", "url_name":"about"},
            # {"name": "简书", "url": "https://www.jianshu.com/u/0582bfa0265d"},
            {"name": "关于", "url_name": "about"},
        ]
        return self.render_string("module/menu.html", menu_list=menu_list)


class SideBarUIModule(tornado.web.UIModule):
    def render(self):
        
        friend_list = [
        ]
        
        owner_info = {
            "name" : settings.name,
            "tags" : settings.owner_tags,
            "slogan" : settings.slogan
        }

        # 可以通过handler获取数量
        statistic = {
            "post": self.handler.get_post_num(),
            "tag": self.handler.get_tag_num(),
            "category": self.handler.get_category_num(),
        }

        return self.render_string("module/sidebar.html", friend_list=friend_list, statistic=statistic, owner_info=owner_info)


class CategoriesHandler(BaseHandler):
    """获取分类列表页面

    Arguments:
        BaseHandler {[type]} -- [description]
    """

    def get(self):
        sql = "select category as name,count(*) as num from post group by category"
        self.cursor.execute(sql)

        categories = self.cursor.fetchall()
        if categories is None:
            categories = []

        categories = sorted(categories, key=lambda category: category['num'], reverse = True)
        self.render("categories.html",
                    categories=categories)


class CategoryHandler(BaseHandler):
    """具体分类下面的日志

    Arguments:
        BaseHandler {[type]} -- [description]
    """

    def get(self, category):

        sql = "select * from post where category = ? order by created desc"
        self.cursor.execute(sql, (category,))
        archive_list = self.cursor.fetchall()

        self.render("page-category.html",
                    archive_list=archive_list, category=category)
class TagHandler(BaseHandler):
    def get(self, tag):
        sql = "select * from tag left join post on post.path = tag.path where tag = ? order by created desc"
        self.cursor.execute(sql, (tag,))
        archive_list = self.cursor.fetchall()

        self.render("page-tag.html",
                    archive_list=archive_list, tag=tag)

class TagsHandler(BaseHandler):
    def get(self):
        sql = "select tag as name,count(*) as num from tag group by tag"
        self.cursor.execute(sql)

        tags = self.cursor.fetchall()
        if tags is None:
            tags = []

        tags = sorted(tags, key=lambda tag: tag['num'], reverse = True)
        self.render("tags.html",
                    tags=tags)

class PostHandler(BaseHandler):
    """获取具体博文
    
    Arguments:
        BaseHandler {[type]} -- [description]
    """

    def get(self, path):
        file_name = os.path.join(main_dir, "post", path) + ".html"

        sql = "select * from post where path = ?"
        self.cursor.execute(sql, (path,))
        article_info = self.cursor.fetchone()

        if article_info is None:
            self.redirect(self.reverse_url("404"))
            return

        get_tags = "select tag from tag where path = ?"
        self.cursor.execute(get_tags, (path,))
        tags = []
        for row in self.cursor.fetchall():
            tags.append(row['tag'])

        get_prev_title = "select path,title from post where path != ? and created <= ? order by created desc limit 1"
        self.cursor.execute(
            get_prev_title, (article_info['path'], article_info['created']))

        get_prev_info = self.cursor.fetchone()
        article_info['prev'] = get_prev_info if get_prev_info else None

        get_next_title = "select path,title from post where path != ? and created > ? order by created asc limit 1"
        self.cursor.execute(
            get_next_title, (article_info['path'], article_info['created']))
        get_next_info = self.cursor.fetchone()
        article_info['next'] = get_next_info if get_next_info else None

        if not os.path.exists(file_name):
            self.redirect(self.reverse_url("404"))
            return

        content = ""
        with open(file_name, "rb") as f:        # 不明白为何要加b
            content = f.read()

        self.render("post-page.html", content=content, tags=tags,**article_info)


def make_app():

    settings = {
        "template_path": os.path.join(os.path.dirname(__file__), "templates"),
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "ui_modules": {'Menu': MenuUIModule, 'SideBar': SideBarUIModule}
    }
    handlers = [
        url(r"/$", PageHandler, name="home"),
        url(r"/index$", IndexHandler, name="index"),
        url(r"/page/(?P<page>\d+)$", PageHandler, name="page"),
        url(r"/about", AboutMeHandler, name="about"),
        url(r"/archive", ArchiveHandler, name='archive'),
        url(r"/categories", CategoriesHandler, name='categories'),
        url(r"/tags", TagsHandler, name='tags'),
        url(r"/post/(?P<path>.*)$", PostHandler, name='post'),
        url(r"/tag/(?P<tag>.*)$", TagHandler, name='tag'),
        url(r"/category/(?P<category>.*)$",
            CategoryHandler, name='category'),          # 可以通过reverse_url("category", "tech")来获取url
        url(r"/notfound", NotFoundHandler, name='404'),
        url(r"/.*", NotFoundHandler, name='notfoud'),
    ]

    app = Application(handlers, **settings)

    return app


def main():
    app = make_app()
    app.listen("5000", "127.0.0.1")
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    # tornado.options.options['log_file_prefix'] = "./logs/test.log"
    # tornado.options.options['log_rotate_mode'] = "time"
    # tornado.options.options['log_rotate_when'] = "M"
    # tornado.options.options['log_rotate_interval'] = 1
    # tornado.options.parse_command_line()
    [i.setFormatter(LogFormatter()) for i in logging.getLogger().handlers]
    main()
