'''
Gets posts from /r/all sorted by hot, if post is not locked, not NSFW
and not in the table, it posts to the specified subreddit.
'''
import praw
from time import sleep, strftime
from datetime import datetime
import sqlite3

'''
Initialise Reddit
Enter user credentials
''' 
reddit = praw.Reddit(client_id='',
                    client_secret='',
                    username='',
                    password='',
                    user_agent='Posts lock threads to specified subreddit by /u/PeskyPotato')


# Subreddit to post to
SUB = 'test'
# Subs to blackslit, e.g. ['test', 'AskReddit']
BLACKLIST = []
# Sleep between searches
SLEEP = 300
# Max size of buffer
BUFFER_SIZE = 5000
# Buffer
buffer = []


'''
Creates a database file and table if one does not already exist.
'''
def createTable():
    conn = sqlite3.connect('posted.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS posts (perma TEXT NOT NULL UNIQUE, title TEXT, udate TEXT, author TEXT, PRIMARY KEY (perma))')
    c.close()
    conn.close()

'''
Writes post to table, if the post exists
returns a 0 if succesfully returns a 1.
'''
def dbWrite(perma, title, udate, author):
    try:
        conn = sqlite3.connect('posted.db')
        c = conn.cursor()
        c.execute("INSERT INTO posts (perma, title, udate, author) VALUES (?, ?, ?, ?)", (perma, title, udate, str(author)))
        conn.commit()
    except sqlite3.IntegrityError:
        c.close()
        conn.close()
        return 0

    c.close()
    conn.close()
    return 1

'''
Checks each submission in the buffer if its not locked, not NSFW and not in blacklist, then calls 
postSub on the submssion.
'''
def checkBuffer():
    for sub_id in buffer:
        print("checking", sub_id, end="\r")
        submission = reddit.submission(id=sub_id)
        if submission.locked and (not submission.over_18) and str(submission.subreddit) not in BLACKLIST:
            postSub(submission)
            with open("stats.csv", "a") as stats:
                stats.write("{},{},{},{}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), submission.subreddit.display_name, submission.permalink, "1"))
            buffer.remove(str(submission.id))

'''
Gets a comment tree
'''
def parse_comment(comment, author, comment_tree, is_root = True):
    comment_author = ""
    try:
        comment_author = comment.author.name
    except AttributeError:
        comment_author = "None"

    if is_root: 
        comment_tree += "    Author: {} Body: {}\n\n".format(comment_author, str(comment.body).replace("\n", "    "))
    else:
        comment_tree += "        Author: {} Body: {}\n\n".format(comment_author, str(comment.body.replace("\n", "       ")))

    for reply in comment.replies:
        if isinstance(reply, praw.models.MoreComments):
            continue
        parse_comment(reply, author, comment_tree, False)
    
    return comment_tree

'''
Posts submission to targetted subreddit if does not exist in the table
'''
def postSub(submission):
    link = "https://reddit.com"+submission.permalink
    title = "{}: {}".format(str(submission.subreddit), submission.title)
    if len(title) > 300:
        title = title[:250] + "..."
    if(dbWrite(submission.permalink, submission.title, submission.created, submission.author)):
        try:
            post = submission.crosspost(SUB, "/r/"+title)
            comment_tree = ""
            for comment in submission.comments:
                if isinstance(comment, praw.models.MoreComments):
                    continue
                if len(comment_tree) > 8500:
                    break
                sleep(1)
                print(comment.body[:10])
                comment_tree = parse_comment(comment, submission.author, comment_tree)
            post.reply("Original post: [{}]({})".format(submission.title, link + "\n\nComments:\n\n" + comment_tree))
        except praw.exceptions.APIException:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "You are doing too much, trying to post again in 15 minutes")
            sleep(900)
            try:
                post = submission.crosspost(SUB, "/r/"+title)
                # avoids comment in case of any error
            except praw.exceptions.APIException as e:
                with ("errors.log", "a+") as f:
                    f.write(e)
                    f.write(submission.permalink)
            post.reply("Original post: [{}]({})".format(submission.title, link))
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Posted",link)
        sleep(60)


'''
Gets posts from /r/all sorted by hot, if post is not locked, not NSFW and not on the blacklist 
then calls postSub on the submission.
'''
def populateBuffer():
    if len(buffer) > BUFFER_SIZE:
        del buffer[:(len(buffer)-BUFFER_SIZE)]
    for submission in reddit.subreddit('all').hot(limit=1000):
        if submission.locked and (not submission.over_18) and str(submission.subreddit) not in BLACKLIST:
            postSub(submission)
            with open("stats.csv", "a") as stats:
                stats.write("{},{},{},{}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), submission.subreddit.display_name, submission.permalink, "0"))
        elif str(submission.id) not in buffer:
            buffer.append(str(submission.id))


'''
Initialise bot
'''
if __name__ == '__main__':
    with open("stats.csv", "w+") as stats:
        stats.write("date,subreddit,perma,buffer\n")
    while(1):
        createTable()
        populateBuffer()
        print("Current buffer:", len(buffer))
        checkBuffer()
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Sleeping for", SLEEP, "seconds.")
        sleep(SLEEP)
