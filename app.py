#!/usr/bin/env python
# encoding: utf-8

import tornado.ioloop
import tornado.httpserver
import tornado.web
from tornado.options import define, options, parse_command_line
from sockjs.tornado import SockJSRouter
from tornado.util import ObjectDict as dict
from handlers import MonitorHandler, MonitorConnection

define("port", default=8888, type=int)


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
    (r"/monitor", MonitorHandler),
    (r"/monitor/(.+)", MonitorHandler),
] + SockJSRouter(MonitorConnection, "/sockjs/monitor").urls)

if __name__ == '__main__':

    parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    print "beanstalk monitor start on 0.0.0.0:%d" % options.port
    tornado.ioloop.IOLoop.instance().start()
