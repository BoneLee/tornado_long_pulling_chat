#!/usr/bin/env python

import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado import autoreload
from tornado.concurrent import Future
import json
import uuid
import logging
from tornado import gen


class MessageBuffer(object):
    def __init__(self):
        self.waiters = {}
        self.cache = []  # TODO add it into redis
        self.cache_size = 200

    def wait_for_message(self, user):
        # Construct a Future to return to our caller.  This allows
        # wait_for_messages to be yielded from a coroutine even though
        # it is not a coroutine itself.  We will set the result of the
        # Future when results are available.
        result_future = Future()
        self.waiters[user] = result_future
        return result_future

    def cancel_wait(self, user):
        if user in self.waiters:
            # Set an empty result to unblock any coroutines waiting.
            self.waiters[user].set_result(None)
            del self.waiters[user]

    def new_message(self, message):
        logging.info("%r listeners online", len(self.waiters))
        if message["type"] == "send_to_all":
            self.send_to_all(message)
        else:
            self.send_to_one(message)
        # TODO add it into redis
        self.cache.append(message)
        if len(self.cache) > self.cache_size:
            self.cache = self.cache[-self.cache_size:]

    def send_to_all(self, message):
        assert message["type"] == "send_to_all"
        for future in self.waiters.values():
            future.set_result(message)
        self.waiters = {}

    def send_to_one(self, message):
        assert message["type"] == "send_to_one"
        user_from = message["from"]
        user_to = message["to"]
        if user_from in self.waiters:
            self.waiters[user_from].set_result(message)
            del self.waiters[user_from]
        if user_to in self.waiters:
            self.waiters[user_to].set_result(message)
            del self.waiters[user_to]
        else:
            # TODO offline message
            pass


class MessageHandler(tornado.web.RequestHandler):
    ERROR = {"NONE": 0, "ARGUMENT_ERR": 1}

    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        # TODO use user token cookie
        user = self.get_argument("user", "")
        if not user:
            self.write(json.dumps({"err": self.ERROR["ARGUMENT_ERR"]}))
            self.finish()
            return
        # Save the future returned by wait_for_messages so we can cancel
        # it in wait_for_messages
        self.user = user
        message = yield self.application.global_message_buffer.wait_for_message(user)
        print "user %s receive message %s" % (user, message)
        if self.request.connection.stream.closed():
            return
        if message:
            self.write(json.dumps(message))
        self.finish()

    def on_connection_close(self):
        self.application.global_message_buffer.cancel_wait(self.user)

    def post(self, *args, **kwargs):
        """
        Post a message here
        """
        user_from = self.get_argument("from", "")
        user_to = self.get_argument("to", "")
        if not user_from:
            self.write(json.dumps({"err": self.ERROR["ARGUMENT_ERR"]}))
            self.finish()
            return
        message = {
            "id": str(uuid.uuid4()),
            "from": user_from,
            "body": self.get_argument("message"),
        }
        if user_to:
            message["to"] = user_to
            message["type"] = "send_to_one"
        else:
            message["type"] = "send_to_all"
        print "message:", message
        self.application.global_message_buffer.new_message(message)
        self.finish()


class MainHandler(tornado.web.RequestHandler):
    """
    The main handler
    """

    def get(self, *args, **kwargs):
        return self.render('index2.html')


class Application(tornado.web.Application):
    """
    This is out application class where we can be specific about  its
    configuration etc.
    """

    def __init__(self):
        handlers = [
            (r'/', MainHandler),
            (r'/message', MessageHandler),
        ]

        # app settings
        settings = {
            'template_path': 'templates',
            'static_path': 'static',
        }
        tornado.web.Application.__init__(self, handlers, **settings)
        # Making this a non-singleton is left as an exercise for the reader.
        self.global_message_buffer = MessageBuffer()


if __name__ == '__main__':
    tornado.options.parse_command_line()
    app = Application()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(8888)
    ioloop = tornado.ioloop.IOLoop.instance()
    autoreload.start(ioloop)
    ioloop.start()
