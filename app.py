#!/usr/bin/env python
# encoding: utf-8

import tornado.ioloop
import tornado.httpserver
import tornado.web
from tornado.options import define, options, parse_command_line
from sockjs.tornado import SockJSRouter, SockJSConnection
import beanstalkt
import uuid
from tornado.util import ObjectDict as dict
from tornado.escape import json_encode, json_decode
from tornado.gen import coroutine, Return
import time

define("port", default=8888, type=int)

REFLASH_FREQUENCY = 2  # seconed


class Clients(object):
    client_id = "{host}:{port}"

    def __init__(self):
        # "host:port": {client:client, browsers=set(}
        self.beanstalk_clients = dict()
        # browser_id: {pages: set(page), clients:set("host:port")}
        self.browsers = dict()
        # self.stats()

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

        # tornado.ioloop.IOLoop.instance().add_timeout(
            # time.time() + REFLASH_FREQUENCY, lambda: self.stats())

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
            #browsers = self.beanstalk_clients[client_id].browsers
            yield client.use(tube)
            job = yield client.stats_job(job_id)
            raise Return(job)

    @coroutine
    def peek_ready(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            #browsers = self.beanstalk_clients[client_id].browsers
            yield client.use(tube)
            rv = yield client.peek_ready()
            raise Return(rv)

    @coroutine
    def peek_delayed(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            #browsers = self.beanstalk_clients[client_id].browsers
            yield client.use(tube)
            rv = yield client.peek_delayed()
            raise Return(rv)

    @coroutine
    def peek_buried(self, client_id, tube):
        if self.beanstalk_clients.get(client_id):
            client = self.beanstalk_clients[client_id].client
            #browsers = self.beanstalk_clients[client_id].browsers
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
            if isinstance(job, beanstalkt.TimedOut): # no job
                return

            yield client.delete(job["id"])

            next_job = yield client.peek_ready()
            if isinstance(job, beanstalkt.CommandFailed): # no job
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
                if isinstance(job, beanstalkt.TimedOut): # no job
                    #message = dict(type="delete-all-ready-jobs-success",
                                #data=tube)
                    #self.broadcast(browsers, message)
                    break

                yield client.delete(job["id"])
                stats_tube = yield client.stats_tube(tube)
                jobs_current = stats_tube["current-jobs-ready"]
                percent = 100.0 * jobs_current / jobs_total
                message = dict(type="delete-ready-job-progress",
                               data=100-percent)
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


class BaseHandler(tornado.web.RequestHandler):

    def get(self):
        self.write("hi")


class MonitorHandler(BaseHandler):

    @coroutine
    def get(self, name=None):
        servers = clients.beanstalk_clients
        if not name:
            self.render("monitor.html", servers=servers)
            return

        tube = self.get_argument("tube", None)
        if tube:
            stats_tube = yield clients.stats_tube(name, tube, False)
            tubes = yield clients.list_tubes(name, False)
            peek_ready = yield clients.peek_ready(name, tube)
            peek_buried = yield clients.peek_buried(name, tube)
            peek_delayed = yield clients.peek_delayed(name, tube)
            if isinstance(peek_ready, beanstalkt.CommandFailed):
                peek_ready = None
            if isinstance(peek_buried, beanstalkt.CommandFailed):
                peek_buried = None
            if isinstance(peek_delayed, beanstalkt.CommandFailed):
                peek_delayed = None
            next_ready_job = None
            next_buried_job = None
            next_delayed_job = None
            if peek_ready:
                next_ready_job = yield clients.stats_job(name, tube, peek_ready["id"])
            if peek_buried:
                next_buried_job = yield clients.stats_job(name, tube, peek_buried["id"])
            if peek_delayed:
                next_delayed_job = yield clients.stats_job(name, tube, peek_delayed["id"])

            self.render("tube.html",
                        name=name,
                        tube_name=tube,
                        stats_tube=stats_tube,
                        tubes=tubes,
                        peek_ready=peek_ready,
                        peek_buried=peek_buried,
                        peek_delayed=peek_delayed,
                        next_ready_job=next_ready_job,
                        next_buried_job=next_buried_job,
                        next_delayed_job=next_delayed_job,
                        servers=servers)
            return

        self.render("server.html", name=name, servers=servers)


class TestHandler(BaseHandler):

    def get(self):
        print clients.browsers
        print clients.beanstalk_clients
        self.write("hi")


class MonitorConnection(SockJSConnection):

    def on_close(self):
        clients.remove_page(self.browser_id, self)
        print "client leave"

    @coroutine
    def on_message(self, message):
        try:
            message = json_decode(message)
        except ValueError:
            return
        data = message["data"]
        msg_type = message["type"]
        print message
        if msg_type == "browser-new":  # client join first
            browser_id = str(uuid.uuid4())
            result = dict(type="client-new",
                          data=dict(
                              id=browser_id
                          ))
            self.send(json_encode(result))

            self.browser_id = browser_id
            clients.add_browser(browser_id, self)
        elif msg_type == "browser-back":
            browser_id = data["id"]

            self.browser_id = browser_id
            clients.add_browser(browser_id, self)
        elif msg_type == "server-add":
            host = data["host"]
            #name = data["name"]
            port = data["port"]
            yield clients.add_client(host, port, self.browser_id)
        elif msg_type == "stats":
            yield clients.stats()
        elif msg_type == "list-tubes":
            #host = data["host"]
            ##name = data["name"]
            #port = data["port"]
            client_id = data
            yield clients.list_tubes(client_id)
        elif msg_type == "stats-tube":
            client_id = data["client_id"]
            tube_name = data["tube_name"]
            yield clients.stats_tube(client_id, tube_name)
        elif msg_type == "refresh-tube":
            client_id = data
            yield clients.auto_refresh_tubes(client_id)
        elif msg_type == "delete-all-ready-jobs":
            client_id = data["client_id"]
            tube_name = data["tube_name"].strip()
            yield clients.delete_all_ready_jobs(client_id, tube_name)
        elif msg_type == "delete-current-ready-job":
            client_id = data["client_id"]
            tube_name = data["tube_name"].strip()
            yield clients.delete_current_ready_job(client_id, tube_name)

        else:
            print "undefined message type:", message["type"]


class Application(tornado.web.Application):

    def __init__(self, handler):
        handlers = handler
        settings = dict(
            debug=True,
            template_path="templates",
            static_path="static",
        )

        super(Application, self).__init__(handlers, **settings)


application = Application([
    (r"/", BaseHandler),
    (r"/monitor", MonitorHandler),
    (r"/monitor/(.+)", MonitorHandler),
    (r"/test", TestHandler),
] + SockJSRouter(MonitorConnection, "/sockjs/monitor").urls)
if __name__ == '__main__':

    parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    print "beanstalk monitor start on 0.0.0.0:%d" % options.port
    tornado.ioloop.IOLoop.instance().start()
