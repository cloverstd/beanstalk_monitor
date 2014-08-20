#!/usr/bin/env python
# encoding: utf-8

import beanstalkt
from tornado.gen import coroutine, Return
from tornado.escape import json_encode
from tornado.util import ObjectDict as dict


class Clients(object):
    client_id = "{host}:{port}"

    def __init__(self):
        # "host:port": {client:client, browsers=set(}
        self.beanstalk_clients = dict()
        # browser_id: {pages: set(page), clients:set("host:port")}
        self.browsers = dict()

    @coroutine
    def add_client(self, host, port, browser_id):

        client_id = self.client_id.format(host=host, port=port)

        if not self.beanstalk_clients.get(client_id):
            client = beanstalkt.Client(host, port)
            self.beanstalk_clients[client_id] = dict(client=client,
                                                     browsers=set())

        self.beanstalk_clients[client_id].browsers.add(browser_id)

        self.browsers[browser_id].clients.add(client_id)
        yield client.connect()

    def remove_page(self, browser_id, page):
        self.browsers[browser_id].pages.discard(page)

    @coroutine
    def stats(self):
        for client_id, item in self.beanstalk_clients.items():
            client = item.client
            browsers = item.browsers
            stats = yield client.stats()
            for browser_id in browsers:
                for page in self.browsers[browser_id].pages:
                    page.send(json_encode({"type": "stats",
                                           "name": client_id,
                                           "data": stats}))

    def broadcast(self, browsers, message):
        if not isinstance(message, str):
            message = json_encode(message)

        for browser_id in browsers:
            for browser_id in browsers:
                for page in self.browsers[browser_id].pages:
                    page.send(message)

    @coroutine
    def list_tubes(self, client_id, broadcast=True):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            browsers = self.beanstalk_clients[client_id].browsers
            tubes = yield client.list_tubes()
            message = {"type": "list-tubes",
                       "name": client_id,
                       "data": tubes}
            if broadcast:
                self.broadcast(browsers, message)
            else:
                raise Return(tubes)

    @coroutine
    def auto_refresh_tubes(self, client_id):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            browsers = self.beanstalk_clients[client_id].browsers
            tubes = yield client.list_tubes()
            for tube in tubes:
                rv = yield client.stats_tube(tube)
                message = {"type": "stats-tube",
                           "data": rv}
                self.broadcast(browsers, message)

    @coroutine
    def stats_tube(self, client_id, tube_name, broadcast=True):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            browsers = self.beanstalk_clients[client_id].browsers
            rv = yield client.stats_tube(tube_name)
            message = {"type": "stats-tube",
                       "data": rv}
            if broadcast:
                self.broadcast(browsers, message)
            else:
                raise Return(rv)

    @coroutine
    def stats_job(self, client_id, tube, job_id):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.use(tube)
            job = yield client.stats_job(job_id)
            raise Return(job)

    @coroutine
    def peek_ready(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.use(tube)
            rv = yield client.peek_ready()
            raise Return(rv)

    @coroutine
    def peek_delayed(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.use(tube)
            rv = yield client.peek_delayed()
            raise Return(rv)

    @coroutine
    def peek_buried(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.use(tube)
            rv = yield client.peek_buried()
            raise Return(rv)

    @coroutine
    def delete_current_ready_job(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.watch(tube)
            job = yield client.reserve(timeout=0)
            browsers = self.beanstalk_clients[client_id].browsers
            if isinstance(job, beanstalkt.TimedOut):  # no job
                return

            yield client.delete(job["id"])

            next_job = yield client.peek_ready()
            if isinstance(next_job, beanstalkt.CommandFailed):  # no job
                message = dict(type="delete-current-ready-job",
                               data=dict(next_job=None))
                self.broadcast(browsers, message)
                return

            job_info = yield client.stats_job(next_job["id"])
            stats_tube = yield client.stats_tube(tube)

            message = dict(type="delete-current-ready-job",
                           data=dict(next_job=job_info,
                                     stats_tube=stats_tube))
            self.broadcast(browsers, message)

    @coroutine
    def delete_all_ready_jobs(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            yield client.watch(tube)
            job = yield client.reserve(timeout=0)
            browsers = self.beanstalk_clients[client_id].browsers

            stats_tube = yield client.stats_tube(tube)
            jobs_total = stats_tube["current-jobs-ready"]
            while job:
                if isinstance(job, beanstalkt.TimedOut):  # no job
                    break

                yield client.delete(job["id"])
                stats_tube = yield client.stats_tube(tube)
                jobs_current = stats_tube["current-jobs-ready"]
                percent = 100.0 * jobs_current / jobs_total
                message = dict(type="delete-ready-job-progress",
                               data=100 - percent)
                self.broadcast(browsers, message)
                job = yield client.reserve(timeout=0)

    def add_browser(self, browser_id, page):
        if not self.browsers.get(browser_id):
            self.browsers[browser_id] = dict(pages=set(),
                                             clients=set(),
                                             )
        self.browsers[browser_id].pages.add(page)
        self.stats()


clients = Clients()
