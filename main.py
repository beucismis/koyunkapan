#!/usr/bin/python3
#-*- encoding:utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import time
import praw
import json
import secrets
import warnings
import numpy as np
from praw.models import Message
from prawcore.exceptions import ServerError
from psaw import PushshiftAPI
from binary_comb import BinComb

warnings.filterwarnings('ignore')

reddit = praw.Reddit(
  "koyunkirpan",
  config_interpolation = "basic"
)

## MAIN CLASS
class runner:
  def __init__(self):
    self.posts              = []
    self.comments           = []
    self.commented_on       = []
    self.flairs             = []
    self.keywords           = []
    self.subreddit          = reddit.subreddit("KGBTR")
    self.working_hours      = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]
    self.forbidden_comments = ['[removed]', '[deleted]', '', ' ', None]
    self.path               = os.getcwd()
    self.search_limit       = 20
    self.post_limit         = 50
    self.alike_value        = 1.35
    self.load_replies()
    self.load_commented_on()

  def load_commented_on(self):
    with open(os.path.join(self.path,'savedata.json'),) as f:
      self.commented_on = json.load(f)

  def on_comment(self, post_id):
    if post_id:
      self.commented_on['ids'].append(post_id)
    with open(os.path.join(self.path, 'savedata.json'), 'w') as json_file:
      json.dump(self.commented_on, json_file, indent=4, sort_keys=True)

  def load_replies(self):
    with open(os.path.join(self.path, 'replies.json'),) as f:
      self.replies = json.load(f)
    if len(self.replies.keys()) == 0:
      self.load_flairs()

  def load_flairs(self):
    for flair in reddit.subreddit("KGBTR").flair.link_templates:
      if flair['id'] not in self.flairs:
        self.replies[flair['id']] = {'text':flair['text'], 'replies':[]}
    with open(os.path.join(self.path, 'replies.json'), 'w') as json_file:
      json.dump(self.replies, json_file, indent=4, sort_keys=True)

  def check_posts(self):
    for submission in self.subreddit.new(limit=self.post_limit):
      if submission not in self.posts and submission.id not in self.commented_on['ids'] and submission.link_flair_text != "Ciddi :snoo_disapproval:":
        self.posts.append(submission)
    for submission in self.subreddit.hot(limit=self.post_limit):
      if submission not in self.posts and submission.id not in self.commented_on['ids'] and submission.link_flair_text != "Ciddi :snoo_disapproval:":
        self.posts.append(submission)
    print("Collected : %s posts\n" %(len(self.posts)))

  def select_post(self):
    for i in range(0, 5):
      p = self.posts[secrets.randbelow(len(self.posts))]
      if len(p.comments) < 5:
        continue
      else:
        return p
    return None

  def post_keywords(self, p):
    for word in p.title.split(" "):
      if word not in self.keywords:
        self.keywords.append(word.lower())
    p.comment_sort = 'best'
    for top_level_comment in p.comments[0:5]:
      if top_level_comment.body not in self.forbidden_comments:
        for word in top_level_comment.body.splitlines()[0].split(" "):
          if word not in self.keywords:
            self.keywords.append(word.lower())
    # Limit Keywors
    self.keywords = self.keywords[0:20]
    # print("KEYWORDS:", self.keywords)

  def find_similar(self, title, nsfw):
    try:
      if nsfw:
        nsfw = "yes"
      else:
        nsfw = "no"
      keywords = title.split(" ")
      return self.subreddit.search("%s nsfw:%s" %(" OR ".join(keywords), nsfw), limit=self.search_limit)
    except ServerError:
      return None

  def comment_fit(self, search_data, id):
    comments = []
    for p in search_data:
      if p.id == id:
        continue
      p.comment_sort = 'best'
      for top_level_comment in p.comments[0:5]:
        cmt = top_level_comment.body.splitlines()[0].lower()
        if cmt not in self.forbidden_comments and len(cmt) > 0:
          self.comments.append(cmt)
    print("Collected : %s comments\n" %(len(self.comments)))

  def compare_sentences(self, s1, s2):
    # Take sentences and split into words
    if type(s1) == list:
      words_1 = s1
    else:
      words_1 = s1.split(" ")
    if type(s2) == list:
      words_2 = s2
    else:
      words_2 = s2.split(" ")
    # Select the sentence with fewer words as words_1
    if len(words_1) >= len(words_2):
      words_3 = words_1
      words_1 = words_2
      words_2 = words_3
    w_ij = np.zeros((len(words_1),len(words_2)), float)
    e_ij = np.zeros((len(words_1),len(words_2)), float)
    for i in range(0, len(words_1)):
      for j in range(0, len(words_2)):
        # compare word lengths
        w_ij[i][j] += abs(len(words_1[i]) - len(words_2[j]))
        # compare word similarities
        word_1 = words_1[i]
        word_2 = words_2[j]
        if len(word_1) >= len(word_2):
          word_3 = word_1
          word_1 = word_2
          word_2 = word_3
        for letter in range(0, len(word_1)):
          if word_1[letter] != word_2[letter]:
            e_ij[i][j] += 1
    total   = np.add(w_ij, e_ij)
    result  = 0
    results = []
    alpha   = len(words_2)/len(words_1)

    # ZERO CHECK
    while np.count_nonzero(total==0) > 0:
      for i in range(0, len(words_1)):
        for j in range(0, len(words_2)):
          if total[i][j] == 0:
            results.append((words_1[i], words_2[j], total[i][j]))
            result += total[i][j]
            total[i] = np.Inf
            total[0][j] = np.Inf

    # REST CHECK
    for i in range(0, len(words_1)):
      if total[i][0] == np.Inf:
          continue
      row_min = 0
      for j in range(0, len(words_2)):
        if total[i][j] < total[i][row_min]:
          row_min = j
      results.append((words_1[i], words_2[row_min], total[i][row_min]))
      result += total[i][row_min]
      total[i] = np.Inf
      total[0][j] = np.Inf
    return result + abs(len(s1)-len(s2))

  def find_best_fit(self, post):
    if len(x.comments) > 0:
      z = np.full((len(x.comments)), np.inf)
      for i in range(0, len(x.comments)):
        z[i] = x.compare_sentences(x.comments[i], x.keywords)

      row_mins = []
      row_min = 0
      for i in range(0, len(x.comments)):
        if z[i] < z[row_min]:
          row_min = i
      for i in range(0, len(x.comments)):
        if z[i] == z[row_min] or z[i] <= round(z[row_min]*self.alike_value):
          row_mins.append(i)
      row_min = row_mins[secrets.randbelow(len(row_mins))]
      cmt = x.comments[row_min]
      print("Best fit (found):", cmt)
      return cmt
    else:
      if post.link_flair_text != None:
        if len(x.replies[post.link_flair_template_id]['replies']) > 0:
          cmt = x.replies[post.link_flair_template_id]['replies'][secrets.randbelow(len(x.replies[post.link_flair_template_id]['replies']))]
          print("Best fit (not found):", cmt)
          return cmt
        else:
          print("No fit :(")
          return None

  def postComment(self, post, cmt):
    if cmt:
      #post.reply(cmt)
      self.on_comment(post.id)
      print("Commented on: %s" %(post.id))

  def doComment(self, post_id):
    self.check_posts()
    post = self.select_post()
    if post_id:
      post = reddit.submission(id=post_id)

    if not post:
      print ("Couldn't find a suitable post :(")
      return

    # print("TITLE      : %s" %(post.title))
    print("POST ID    : %s" %(post.id))
    print("URL        : https://reddit.com%s\n" %(post.permalink))

    self.post_keywords(post)

    print("Searching similar posts...\n")
    similars = self.find_similar(post.title, post.over_18)
    if similars:
      self.comment_fit(similars, post.id)

    cmt = self.find_best_fit(post)

    self.postComment(post, cmt)

  def reply_on_comment(self, id):
    api = PushshiftAPI(reddit)
    original_comment = reddit.comment(id)

    all_comments = []
    comments     = []
    keywords     = original_comment.body.split()
    x            = BinComb(keywords)
    searches     = x.get_combinations()

    print ("Comment:", original_comment.body)
    print ("Searches:", len(searches))

    #SEARCHING AND COLLECTING COMMENTS
    for search in searches:
      print("\nStarting search %s:" %(searches.index(search)+1))
      comments.append([])
      gen   = api.search_comments(q=search, subreddit='KGBTR')
      cache = []

      for comment in gen:
        if len(cache) > 500:
          break
        if comment.body == '[deleted]' or comment.body == '[removed]':
          continue
        if len(comment.body.split()) >= len(keywords)*3:
          continue
        if comment.id == original_comment.id:
          continue
        if comment not in all_comments:
          cache.append(comment)

      comments[searches.index(search)] += cache
      all_comments += cache
      if len(cache) > 2:
        break

    print("\nENDED.")

    for result in comments:
      print("Length:", len(result))
      c = None
      if len(result) > 0:
        tries = 0
        while True:
          if len(result) == 0:
            break
          c = result[secrets.randbelow(len(result))]
          c.refresh()
          if len(c.replies) >= 1:
            break
          else:
            result.remove(c)
            c = None
      if c:
        break

    if c:
      print (c.id)
      print ('https://www.reddit.com'+c.permalink)
      print ("REPLIES:", len(c.replies), "\n")
      to_comment = []
      for reply in c.replies:
        if reply.body not in self.forbidden_comments:
          to_comment.append(reply.body)
      original_comment.reply(to_comment[secrets.randbelow(len(to_comment))])
    else:
      print("No comment found :(")

if __name__ == '__main__':
  x = runner()

  arg = sys.argv[1:]

  if len(arg) > 0:
    if '-i' in arg:
      post_id = arg[arg.index('-i')+1]
      x.doComment(post_id)
    if '--id' in arg:
      post_id = arg[arg.index('--i')+1]
      x.doComment(post_id)
  else:
    print("Starting script...\n")
    if time.strftime("%H") in x.working_hours:
      try:
        x.doComment(None)
      except Exception as e:
        print("Exception found.", str(e))
    else:
      print("Sorry, not in working hours.")

  for item in reddit.inbox.unread(limit=None):
    item.mark_read()
    Message.mark_read(item)
    if item.type == "comment_reply":
      if item.author != "indirbeni":
        x.reply_on_comment(item.id)
