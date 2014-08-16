#!/usr/bin/env python
# encoding: utf-8

import uuid
import beanstalkt
import tornado.web
from clients import clients
from tornado.gen import coroutine
from tornado.escape import json_encode, json_decode
from tornado.util import ObjectDict as dict
from sockjs.tornado import SockJSConnection


class MonitorHandler(tornado.web.RequestHandler):

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
        print message["type"]
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
            port = data["port"]
            yield clients.add_client(host, port, self.browser_id)
        elif msg_type == "stats":
            yield clients.stats()
        elif msg_type == "list-tubes":
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
