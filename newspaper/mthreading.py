# -*- coding: utf-8 -*-
"""
Anything that has to do with threading in this library
must be abstracted in this file. If we decide to do gevent
also, it will deserve its own gevent file.
"""
__title__ = 'newspaper'
__author__ = 'Lucas Ou-Yang'
__license__ = 'MIT'
__copyright__ = 'Copyright 2014, Lucas Ou-Yang'

import queue
import traceback
from threading import Thread

from .configuration import Configuration


class Worker(Thread):
    """
    Thread executing tasks from a given tasks queue.
    """
    def __init__(self, tasks, timeout_seconds):
        Thread.__init__(self)
        self.tasks = tasks
        self.timeout = timeout_seconds
        self.daemon = True
        self.start()

    def run(self):
        while True:
            try:
                func, args, kargs = self.tasks.get(timeout=self.timeout)
            except queue.Empty:
                # Extra thread allocated, no job, exit gracefully
                break
            try:
                func(*args, **kargs)
            except Exception:
                traceback.print_exc()

            self.tasks.task_done()


class ThreadPool:
    def __init__(self, num_threads, timeout_seconds):
        self.tasks = queue.Queue(num_threads)
        for _ in range(num_threads):
            Worker(self.tasks, timeout_seconds)

    def add_task(self, func, *args, **kargs):
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        self.tasks.join()


class NewsPool(object):

    def __init__(self, config=None):
        """
        Abstraction of a threadpool. A newspool can accept any number of
        source OR article objects together in a list. It allocates one
        thread to every source and then joins.

        We allocate one thread per source to avoid rate limiting.
        5 sources = 5 threads, one per source.

        >>> import newspaper
        >>> from newspaper import news_pool

        >>> cnn_paper = newspaper.build('http://cnn.com')
        >>> tc_paper = newspaper.build('http://techcrunch.com')
        >>> espn_paper = newspaper.build('http://espn.com')

        >>> papers = [cnn_paper, tc_paper, espn_paper]
        >>> news_pool.set(papers)
        >>> news_pool.join()

        # All of your papers should have their articles html all populated now.
        >>> cnn_paper.articles[50].html
        u'<html>blahblah ... '
        """
        self.papers = []
        self.articles = []
        self.pool = None
        self.config = config or Configuration()

    def join(self):
        """
        Runs the mtheading and returns when all threads have joined
        resets the task.
        """
        if self.pool is None and self.articles is None:
            print('Call set_papers(..) or set_articles(...) with a list of source '
                  'objects before .join(..)')
            raise
        self.pool.wait_completion()
        self.papers = []
        self.articles = []
        self.pool = None

    def set_papers(self, paper_list, threads_per_source=1):
        self.papers = paper_list
        num_threads = threads_per_source * len(self.papers)
        timeout = self.config.thread_timeout_seconds
        self.pool = ThreadPool(num_threads, timeout)

        for paper in self.papers:
            self.pool.add_task(paper.download_articles)

    def set_articles(self, article_list):
        self.articles = article_list
        timeout = self.config.thread_timeout_seconds
        num_threads = len(self.articles) if len(self.articles <= self.config.max_number_threads) else self.config.max_number_threads
        self.pool = ThreadPool(num_threads, timeout)

        for article in self.articles:
            self.pool.add_task(article.download)
            self.pool.add_task(article.parse)
