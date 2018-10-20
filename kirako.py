"""
./post/ 存储渲染后的博客文件
./source/ 博客源文件
./post.db  存储博客相关信息
"""
import argparse
import os
import datetime
import shutil
import sqlite3
import settings

from utility import analyze_post

POST_INFO_SEPERATE = "=" * 60
READ_MORE_TAG = "<!--more-->"
SOURCE_SUFFIX = ["md"]

create_post_sql = """
CREATE TABLE post(
    path CHAR(256) PRIMARY KEY  NOT NULL,
    title CHAR(256)  NOT NULL,
    created DATETIME NOT NULL,
    description TEXT NOT NULL,
    category CHAR(256) NOT NULL
)
"""

insert_post_sql_pattern = """
INSERT INTO post VALUES (?,?,?,?,?)
"""

create_tag_sql = """
CREATE TABLE tag(
    path CHAR(256) NOT NULL,
    tag CHAR(256) NOT NULL
)
"""

insert_tag_sql_pattern = """
    INSERT INTO tag VALUES (?,?)
"""

def new(filename, dir, suffix = "md"):

    filename = filename + "." + suffix
    full_filename = os.path.join(dir,"source",filename)

    exist_files = os.listdir(dir)

    if filename in exist_files:
        raise Exception("文件{filename}已存在".format(filename=filename))

    with open(full_filename, "w", encoding="utf-8") as f:
        meta = [
            "Title: here is title",
            "Date: {now}".format(
                now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "Category: 未分类",
            "Tag: 无标签"
        ]

        f.write("\n".join(meta))
        f.write("\n")
        f.write(POST_INFO_SEPERATE)           # 文章信息分隔符
        f.write("\n")
        f.write("Write description here...\n")
        f.write(READ_MORE_TAG)      # Read more 分隔符
        f.write("\n")
        f.write("Write start here....")

def delete_old_blog_dir(dir):
    """删除旧的博客渲染文件
    
    Arguments:
        dir {[type]} -- [description]
    """

    post_filename = os.path.join(dir, "post")
    if os.path.exists(post_filename):
        shutil.rmtree(post_filename)

def make_new_blog_dir(dir):
    """创建存储渲染文件的文件夹
    
    Arguments:
        dir {[type]} -- [description]
    """

    post_filename = os.path.join(dir, "post")

    if os.path.exists(post_filename):
        shutil.rmtree(post_filename)
    
    os.mkdir(post_filename)

def delete_old_db(dir, db_name):
    """删除旧的db
    
    Arguments:
        dir {[type]} -- [description]
        db_name {[type]} -- [description]
    """

    db_filename = os.path.join(dir, db_name)

    if os.path.exists(db_filename):
        os.unlink(db_filename)

def make_new_db(dir, db_name):
    """创建新db
    
    Arguments:
        dir {[type]} -- [description]
        db_name {[type]} -- [description]
    """

    db_filename = os.path.join(dir, db_name)
    db = sqlite3.connect(db_filename)

    c = db.cursor()

    c.execute(create_post_sql)
    c.execute(create_tag_sql)
    db.commit()
    db.close()

def save_info_to_db(dir, db_name, article_component_list):
    """存储博客信息
    
    Arguments:
        dir {[type]} -- [description]
        db_name {[type]} -- [description]
        article_component_list {[type]} -- [description]
    """

    db_filename = os.path.join(dir, db_name)
    db = sqlite3.connect(db_filename)

    c = db.cursor()

    for article_component in article_component_list:
        created = article_component["date"].strftime("%Y-%m-%d %H:%M:%S")
        description = article_component["description"]
        path = article_component["date"].strftime(
            "%Y-%m-%d-") + article_component["title"]
        title = article_component["title"]
        category = article_component["category"]

        c.execute(insert_post_sql_pattern,
                (path, title, created, description, category))

        for tag in article_component["tag"]:
            c.execute(insert_tag_sql_pattern, (path, tag))
   
    db.commit()
    db.close()

def render_blog(dir, article_component_list):
    """渲染博客文件
    
    Arguments:
        dir {[type]} -- [description]
        article_component_list {[type]} -- [description]
    """

    post_filename = os.path.join(dir, "post")

    for article_component in article_component_list:
        path = article_component["date"].strftime(
            "%Y-%m-%d-") + article_component["title"]

        with open(os.path.join(post_filename, path + ".html"), "w") as fp:
            fp.write(article_component["content"])

def build(dir, db_name):
    #删除旧文件 
    delete_old_blog_dir(dir)
    delete_old_db(dir, db_name)

    #创建新文件
    make_new_blog_dir(dir)
    make_new_db(dir, db_name)

    article_component_list = []
    source_path = os.path.join(dir, "source")
    files = os.listdir(source_path)
    for file in files:
        if not file.endswith("md"):
            continue
            
        file = os.path.join(source_path, file)
        with open(file, "r") as fp:
            content = fp.read()
            content = content.strip()
            article_component = analyze_post(content)
            # print(article_component)
            article_component_list.append(article_component)

    #存储文件
    save_info_to_db(dir, db_name, article_component_list)
    render_blog(dir, article_component_list)

def main():
    parser = argparse.ArgumentParser(description='kirako blog management tools')

    parser.add_argument(
        "-n", "--new",  help="Create a new post at source directory", metavar="FILENAME")
    parser.add_argument("--suffix", help ="Give post suffix, default:md", default =  "md")
    parser.add_argument("--workdir", help="Give work directory, default:cwd ", default = os.getcwd())
    parser.add_argument("--build", help="Build Blog",
                        default=False, action="store_true")
    parser.add_argument("--db_name", help="Build destination db", default = "post.db" )

    args = parser.parse_args()

    if args.new:
        filename = args.new
        suffix = args.suffix
        dir = args.workdir
        new(filename, dir, suffix)
    elif args.build:
        dir = args.workdir
        db_name = args.db_name
        build(dir, db_name)

if __name__ == "__main__":
    main()
