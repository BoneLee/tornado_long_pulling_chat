$(document).ready(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};

    $("#messageform").click(function() {
        newMessage($(this));
        return false;
    });
    $("#message").select();
    updater.poll();
});

function newMessage(form) {
    var message = form.formToDict();
    var disabled = form.find("input[type=submit]");
    disabled.disable();
    $.postJSON("/message", message, function(response) {
        updater.showMessage(response);
        if (message.id) {
            form.parent().remove();
        } else {
            form.find("input[type=text]").val("").select();
            disabled.enable();
        }
    });
}

function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}

jQuery.postJSON = function(url, args, callback) {
    args._xsrf = getCookie("_xsrf");
    $.ajax({url: url, data: $.param(args), dataType: "text", type: "POST",
            success: function(response) {
                if (response && callback) callback(response);
    }, error: function(response) {
        console.log("ERROR:", response)
    }});
};

jQuery.fn.formToDict = function() {
    var fields = this.serializeArray();
    var json = {}
    for (var i = 0; i < fields.length; i++) {
        json[fields[i].name] = fields[i].value;
    }
    if (json.next) delete json.next;
    return json;
};

jQuery.fn.disable = function() {
    this.enable(false);
    return this;
};

jQuery.fn.enable = function(opt_enable) {
    if (arguments.length && !opt_enable) {
        this.attr("disabled", "disabled");
    } else {
        this.removeAttr("disabled");
    }
    return this;
};

var updater = {
    errorSleepTime: 500,
    cursor: null,

    poll: function() {
        var args = {"_xsrf": getCookie("_xsrf")};
        if (updater.cursor) args.cursor = updater.cursor;
        $.ajax({url: "/message", type: "GET", dataType: "text",
                data: $.param(args), success: updater.onSuccess,
                error: updater.onError});
    },

    onSuccess: function(response) {
        try {
            updater.newMessage(JSON.parse(response));
        } catch (e) {
            console.log("response err:", e);
            updater.onError();
            return;
        }
        updater.errorSleepTime = 500;
        window.setTimeout(updater.poll, 0);
    },

    onError: function(response) {
        updater.errorSleepTime *= 2;
        console.log("Poll error; sleeping for", updater.errorSleepTime, "ms");
        window.setTimeout(updater.poll, updater.errorSleepTime);
    },

    newMessage: function(response) {
        updater.cursor = response.cursor;
        var message = response.body;
        updater.cursor = response.id;
        updater.showMessage(message);
    },

    showMessage: function(message) {
        $("#inbox").append("<p>"+message+"</p>");
    }
};
