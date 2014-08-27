  var conn = null;
  if (!store.get("table-names")) {
      store.set("table-names", ["current-connections",
                                "current-jobs-buried",
                                "current-jobs-delayed",
                                "current-jobs-ready",
                                "current-jobs-reserved",
                                "current-jobs-urgent",
                                "current-tubes",
                                "current-waiting"]);
  }
  if (!store.get("server-table-names")) {
      store.set("server-table-names", ["current-jobs-delayed",
                                "current-jobs-ready",
                                "current-jobs-reserved",
                                "current-jobs-buried",
                                "current-jobs-urgent",
                                "total-jobs"]);
  }
  if (!store.get("tube-table-names")) {
      store.set("tube-table-names", ["current-jobs-delayed",
                                "current-jobs-ready",
                                "current-jobs-reserved",
                                "current-jobs-buried",
                                "current-jobs-urgent",
                                "total-jobs"]);
  }
  var connect = function(callback) {
      var conn = new SockJS("/sockjs/monitor");

      conn.onopen = function() {
          console.log("open");
          var browser_id = store.get("browser_id");

          if (browser_id === undefined) {
              conn.send(JSON.stringify({
                      type: "browser-new",
                      data: null
                  }));
          } else {
              conn.send(JSON.stringify({
                      type: "browser-back",
                      data: {
                          id: browser_id,
                          servers: null
                      }
                  }));
          }
          if (typeof callback === "function") {
              callback();
          }
      };
      conn.onmessage = function(e) {
          console.log("message:", e.data);
          var message = JSON.parse(e.data);
          switch(message.type) {
              case "client-new":
                  store.set("browser_id", message.data.id);
                  break;
              case "stats":
                  updateServerBox(message.name, message.data);
                  break;
              case "list-tubes":
                  updateTubesList(message.data);
                  break;
              case "stats-tube":
                  // TODO: delete not use tube
                  updateTube(message.data);
                  break;
              case "delete-all-ready-jobs-success":
                break;
              case "delete-ready-job-progress":
              case "delete-delayed-job-progress":
              case "delete-buried-job-progress":
               var type;
                switch (message.type) {
                  case "delete-ready-job-progress":
                    type = "ready";
                    break;
                  case "delete-delayed-job-progress":
                    type = "delayed";
                    break;
                  case "delete-buried-job-progress":
                    type = "buried";
                    break;
                }
                var percent = String(message.data).slice(0, 2) + "%";
                $("#delete-all-" + type + "-jobs-progress").find(".uk-progress-bar").width(percent);
                $("#delete-all-" + type + "-jobs-progress").find(".uk-progress-bar").text(percent);
                if (message.data == 100) {
                  if (current == "tube") {
                    window.location.reload();
                  }
                  $("#delete-all-" + type + "-jobs-progress").fadeOut();
                  $.UIkit.notify({
                      message: "<i class='uk-icon-check'></i> Delete all jobs of " + message.data + ".",
                      status: 'success',
                      timeout: 5000,
                      pos: 'bottom-right'
                  });
                }
                break;
              case "delete-current-ready-job":
              case "delete-current-delayed-job":
              case "delete-current-buried-job":
                if (message.data.next_job) {
                  $.each(message.data.next_job, function(key, value) {
                    var td;
                    switch (message.type) {
                      case "delete-current-delayed-job":
                        td = $("#delayed-job-status td[name=" + key + "]");
                        break;
                      case "delete-current-ready-job":
                        td = $("#ready-job-status td[name=" + key + "]");
                        break;
                      case "delete-current-buried-job":
                        td = $("#buried-job-status td[name=" + key + "]");
                        break;
                    }
                    var color = td.css('background-color');
                    if (td.data("prev") != value) {
                      td.css({
                                  'background-color': '#afa'
                          }).animate({
                                  'background-color': color
                          }, 500);
                    }
                    td.text(value);
                    td.data("prev", value);
                  });
                  $.each(message.data.stats_tube, function(key, value) {
                    var td = $("td[name=" + key + "]");
                    var color = td.css('background-color');
                    if (td.data("prev") != value) {
                      td.css({
                                  'background-color': '#afa'
                          }).animate({
                                  'background-color': color
                          }, 500);
                    }
                    td.text(value);
                    td.data("prev", value);
                  });
                } else {
                  window.location.reload();
                }
                break;
              default:
                  break;
          }
      };
      conn.onclose = function() {
          console.log("close");
      };
      return conn;
  };

  var updateTubesList = function(tubes) {
    var $tbody = $("#tube-box tbody");
    var th = $("#tube-box thead").find("th");

    var tableNames = store.get("server-table-names");
    $.each(tubes, function(index, e) {
      $(".tube-menu-list").append($("<li><a href='?tube=" + e + "'>" + e + "</a></li>"));
      var $tr = $("<tr></tr>");
      $.each(th, function() {
        var $td = $("<td></td>");
        $td.text("0");
        $td.attr("name", $(this).attr("name"));
        if ($.inArray($(this).attr("name"), tableNames) != -1) {
            $td.show();
        } else {
            $td.hide();
        }
        $tr.append($td);
      });
      $tr.find("td").eq(0).html('<a href="?tube=' + e + '">' + e + '</a>').show();
      $tr.data("name", e);
      $tr.appendTo($tbody);
      conn.send(JSON.stringify({"type": "stats-tube",
                                "data": {
                                  client_id: $(".server-name").data("name"),
                                  tube_name: e
                                }
      }))
    });
  };

  var updateTube = function(tube) {
    var $tbody = $("#tube-box tbody");
    var tr = $tbody.find("tr");
    var updateFlag = false;
    $.each(tr, function(i, e) {
      var name = $(this).data("name");
      if (name == tube.name) {
        updateFlag = true;
        var td = $(this).find("td");
        for (var i = 0; i < td.length; i++) {
          $.each(tube, function(key, value) {
            if (key == td.eq(i).attr("name")) {
              var text = td.eq(i).text();
              var color = td.eq(i).css('background-color');
              if (td.eq(i).data("prev") != value) {
                td.eq(i).css({
                            'background-color': '#afa'
                    }).animate({
                            'background-color': color
                    }, 500);
              } else {
                //td.css({"background-color": color});
              }
              td.eq(i).text(value);
              td.eq(i).data("prev", value);
            }
          });
          td.eq(0).html('<a href="?tube=' + tube.name + '">' + tube.name + '</a>').show();
        }
      }
    });
    if (!updateFlag) {
      var $tbody = $("#tube-box tbody");
      var th = $("#tube-box thead").find("th");
      var $tr = $("<tr></tr>");
      var tableNames = store.get("server-table-names");
      $.each(th, function() {
        var $td = $("<td></td>");
        $td.text("0");
        $td.attr("name", $(this).attr("name"));
        if ($.inArray($(this).attr("name"), tableNames) != -1) {
            $td.show();
        } else {
            $td.hide();
        }
        $tr.append($td);
      });
      $tr.find("td").eq(0).html('<a href="?tube=' + tube.name + '">' + tube.name + '</a>').show();
      $tr.data("name", tube.name);
      $tr.appendTo($tbody);
    }
  };
  var timer;
  var doAutoRefresh = false;
  var autoRefreshTube = function() {
    conn.send(JSON.stringify({"type": "refresh-tube",
                             "data": $(".server-name").data("name")}));
    timer = setTimeout(autoRefreshTube, 1000);
  };

  var addServerToBox = function(data, callback) {
      var $tbody = $("#servers-box tbody");
      var $thead = $("#servers-box thead");
      var th = $thead.find("th");
      var $tr = $("<tr></tr>");
      var $td_name = $("<td></td>");
      $td_name.html('<a href="/monitor/' + data.host + ":" + data.port + '">' + data.name + '</a>');
      /*$td_name.data("name", data.host + ":" + data.port);*/
      $tr.data("name", data.host + ":" + data.port);
      $tr.append($td_name);
      var tableNames = store.get("table-names");
      for (var i = 1; i < th.length - 1; i++) {
          var $td = $("<td></td>");
          $td.attr("name", th.eq(i).attr("name"));
          if ($.inArray(th.eq(i).attr("name"), tableNames) != -1) {
              $td.show();
          } else {
              $td.hide();
          }
          $td.text("0");
          $td.appendTo($tr);
      }
      $tr.append($('<td><button type="button" class="uk-button uk-button-danger uk-button-mini remove-server"><i class="uk-icon-minus"></i></button></td>'));
      $tr.appendTo($tbody);
      $(".server-menu-list").append($('<li><a href="/monitor/' + data.host + ":" + data.port + '">' + data.name + '</a></li>'));
      if (typeof callback === "function") {
          callback();
      }
      conn.send(JSON.stringify({
              type: "stats",
              data: null
          }));
  };
  var updateServerBox = function(name, stats) {
      var $tbody = $("#servers-box tbody");
      var tr = $tbody.find("tr");
      for (var i = 1; i < tr.length; i++) {
          if (tr.eq(i).data("name") == name) {
              var td = tr.eq(i).find("td");
              for (var j = 1; j < td.length-1; j++) {
                  /*console.log(j);*/
                  /*console.log(td.eq(j).attr("name"));*/
                  var $td = td.eq(j);
                  var prev_value = $td.text();
                  if (prev_value != stats[$td.attr("name")]) {
                      $td.text(stats[$td.attr("name")]);
                  } else {
                  }
              }
          }
      }
  };

  var init = function() {
      var serversList = store.get("servers-list");
      if (serversList) {
          for (var i = 0 ;i < serversList.length; i++) {
              addServer(serversList[i]);
          }
      }
      var names = null;
      switch (current) {
        case "server":
          names = store.get("server-table-names");
          break;
        case "monitor":
          names = store.get("table-names");
          break;
        case "tube":
          names = store.get("tube-table-names");
      }
      conn.send(JSON.stringify({"type": "list-tubes",
                                "data": $(".server-name").data("name")
      }))
      var $thead = $("#servers-box thead");
      var th = $thead.find("th");
      for (var i = 1; i < th.length - 1; i++) {
          if ($.inArray(th.eq(i).attr("name"), names) != -1) {
              th.eq(i).show();
          } else {
              th.eq(i).hide();
          }
      }
      $.each(names, function(index, element) {
          $("table").find("[name=" + element + "]").show();
          $("#filter-columns-modal").find("input[name=" + element + "]").prop("checked", true);
      });
  };
  var addServer = function(data) {
      conn.send(JSON.stringify({
              type: "server-add",
              data: data
          }));
      addServerToBox(data);
  };

  $(function() {
      conn = connect(function() {
        if (current != "tube") {
          init();
        } else {
          $("#filter").hide();
          var serverList = store.get("servers-list");
          var $ul = $(".server-menu-list");
          $.each(serverList, function(i, e) {
            $ul.append("<li><a href='/monitor/" + e.host + ":" + e.port + "'>" + e.name + "</a></li>");
          });
        }
      });
      $("#filter-columns-modal").on("click", "input[type=checkbox]", function() {
          $("table").find("[name=" + $(this).attr("name") + "]").toggle($(this).is(':checked'));
          var names = [];
          $("#filter-columns-modal input:checked").each(function() {
              names.push($(this).attr('name'));
          });
          if (current == "server") {
            store.set("server-table-names", names);
          } else if (current == "monitor") {
            store.set("table-names", names);
          } else if (current == "tube") {
            store.set("tube-table-names", names);
          }
      });
      $(document).on("click", "#auto-refresh", function() {
        if ($(this).hasClass("uk-active")) {
          doAutoRefresh = false;
          clearTimeout(timer);
          $(this).removeClass("uk-active");
        } else {
          doAutoRefresh = true;
          $(this).addClass("uk-active");
          autoRefreshTube();
        }
      });
      $(document).on("click", ".remove-server", function() {
          conn.send(JSON.stringify({
                  type: "stats",
                  data: null
              }));
          var serversList = store.get("servers-list");
          var index = $(this).parent().parent().index();
          serversList.splice(index-1, 1);
          store.set("servers-list", serversList);
          $(".server-menu-list li").eq(index-1).remove();
          $(this).parent().parent().toggle(function() {
              $(this).remove();
          });
      });
      $(document).on("click", "#add-server-button", function() {
          var newServerName = $("#new-server-name").val();
          var newServerHost = $("#new-server-host").val();
          var newServerPort = $("#new-server-port").val();

          var host = newServerHost ? newServerHost : "localhost";
          var port = newServerPort ? newServerPort : 11300;
          var name = newServerName ? newServerName : host + ":" + port;

          var data = {
              name: name,
              host: host,
              port: port
          };
          conn.send(JSON.stringify({
                  type: "server-add",
                  data: data
                  }));

          var serversList = store.get("servers-list");
          if (serversList) {
              serversList.push(data);
          } else {
              serversList = [data];
          }
          store.set("servers-list", serversList);

          var modal = $.UIkit.modal("#add-server-modal");
          addServerToBox(data, function() {
              modal.hide();
          });
      });
      $(document).on("click", "#delete-all-ready-jobs", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          $("#delete-all-ready-jobs-progress").fadeIn();
          $("#delete-all-ready-jobs-progress").find(".uk-progress-bar").text("0%");
          conn.send(JSON.stringify({
                  type: "delete-all-ready-jobs",
                  data: data
                  }));
      });
      $(document).on("click", "#delete-current-ready-job", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          conn.send(JSON.stringify({
                  type: "delete-current-ready-job",
                  data: data
                  }));
      });
      $(document).on("click", "#delete-current-delayed-job", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          conn.send(JSON.stringify({
                  type: "delete-current-delayed-job",
                  data: data
                  }));
      });
      $(document).on("click", "#delete-all-delayed-jobs", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          $("#delete-all-delayed-jobs-progress").fadeIn();
          $("#delete-all-delayed-jobs-progress").find(".uk-progress-bar").text("0%");
          conn.send(JSON.stringify({
                  type: "delete-all-delayed-jobs",
                  data: data
                  }));
      });
      $(document).on("click", "#delete-current-buried-job", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          conn.send(JSON.stringify({
                  type: "delete-current-buried-job",
                  data: data
                  }));
      });
      $(document).on("click", "#delete-all-buried-jobs", function() {
          var data = {
            client_id: $(".server-name").data("name"),
            tube_name: $("td[name=name]").text()
          };
          $("#delete-all-buried-jobs-progress").fadeIn();
          $("#delete-all-buried-jobs-progress").find(".uk-progress-bar").text("0%");
          conn.send(JSON.stringify({
                  type: "delete-all-buried-jobs",
                  data: data
                  }));
      });
  });
