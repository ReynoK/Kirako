import os
import sqlite3
import shutil
from utility import analyze_post

main_dir = os.getcwd()
path = os.path.join(main_dir, "source")
post_bk = os.path.join(main_dir, "post_bk")
post_dir = os.path.join(main_dir, "post")

post_db = os.path.join(main_dir, "post.db")
post_db_temp = post_db + ".temp"



os.chdir(path)
files = os.listdir("./")
article_component_list = []

os.mkdir(post_bk)

db = sqlite3.connect(post_db_temp)
c = db.cursor()

c.execute(create_post_sql)
c.execute(create_tag_sql)
db.commit()

for file in files:
    file = os.path.join(main_dir, "source", file)
    with open(file, "r") as fp:
        content = fp.read()
        content = content.strip()
        article_component = analyze_post(content)
        # print(article_component)
        article_component_list.append(article_component)

for article_component in article_component_list:
    post_table_name = "POST_tmp"
    created = article_component["date"].strftime("%Y-%m-%d %H:%M:%S")
    description = article_component["description"]
    path = article_component["date"].strftime("%Y-%m-%d-") + article_component["title"]
    title = article_component["title"]
    category = article_component["category"]

    c.execute(insert_post_sql_pattern, (path,title, created, description, category))

    for tag in article_component["tag"]:
        c.execute(insert_tag_sql_pattern, (path, tag))

    with open(os.path.join(post_bk, path) + ".html", "w") as fp:
        fp.write(article_component["content"])
db.commit()
# db.close()

if os.path.exists(post_dir):
    shutil.rmtree(post_dir)
os.rename(post_bk, post_dir)

if os.path.exists(post_db):
    os.unlink(post_db)

os.rename(post_db_temp, post_db)

def dict_factory(cursor, row):
  d = {}
  for idx, col in enumerate(cursor.description):
    d[col[0]] = row[idx]
  return d

db.row_factory = dict_factory
c = db.cursor()

c.execute("select * from post")
print(c.fetchmany())