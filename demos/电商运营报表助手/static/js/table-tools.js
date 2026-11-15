/* ── 表格工具脚本 ── */
/* 作用：处理列宽拖动、内容自适应、列宽保存与当前页全选。 */
/* 表格列宽拖动、列宽记忆、当前页全选与批量按钮联动 */
/* 页面脚本：初始化当前页交互。 */
(function () {
  "use strict";

  /* widthOf：处理对应交互。 */
  function widthOf(col, fallback) {
    var value = parseInt(col.style.width, 10);
    return isNaN(value) ? fallback : value;
  }

  /* applyWidths：处理对应交互。 */
  function applyWidths(cols, widths) {
    cols.forEach(function (col, i) {
      if (widths[i]) { col.style.width = widths[i] + "px"; }
    });
  }

  /* initResizable：处理对应交互。 */
  function initResizable(table) {
    var key = table.getAttribute("data-resizable") || table.id;
    var cols = Array.prototype.slice.call(table.querySelectorAll("colgroup col"));
    if (!cols.length) { return; }
    var defaults = cols.map(function (col) { return widthOf(col, 100); });
    var stored = null;
    try { stored = JSON.parse(window.localStorage.getItem("colwidth:" + key) || "null"); }
    catch (err) { stored = null; }
    if (Array.isArray(stored) && stored.length === cols.length) {
      applyWidths(cols, stored);
    }
    var headers = Array.prototype.slice.call(table.querySelectorAll("thead th"));
    var canvas = document.createElement("canvas");
    var context = canvas.getContext("2d");

    /* measure：处理对应交互。 */
    function measure(text, th) {
      var style = window.getComputedStyle(th);
      context.font = style.fontWeight + " " + style.fontSize + " " + style.fontFamily;
      return context.measureText(text).width;
    }

    /* autoFit：处理对应交互。 */
    function autoFit(index) {
      var th = headers[index];
      var maxWidth = measure((th.textContent || "").trim(), th) + 34;
      var cells = table.querySelectorAll("tbody tr");
      cells.forEach(function (row) {
        var cell = row.children[index];
        if (cell) {
          maxWidth = Math.max(maxWidth, measure((cell.innerText || "").trim(), th) + 26);
        }
      });
      cols[index].style.width = Math.max(60, Math.ceil(maxWidth)) + "px";
      saveWidths();
    }

    /* saveWidths：处理对应交互。 */
    function saveWidths() {
      var widths = cols.map(function (col, i) { return widthOf(col, defaults[i]); });
      try { window.localStorage.setItem("colwidth:" + key, JSON.stringify(widths)); }
      catch (err) { /* 本地存储不可用时保留当前会话 */ }
    }

    headers.forEach(function (th, index) {
      if (!cols[index]) { return; }
      th.classList.add("has-resizer");
      th.title = "拖动右侧边线调整列宽，双击自动适应内容";
      var handle = document.createElement("span");
      handle.className = "col-resizer";
      handle.setAttribute("aria-hidden", "true");
      th.appendChild(handle);
      handle.addEventListener("dblclick", function (event) {
        event.preventDefault();
        event.stopPropagation();
        autoFit(index);
      });
      th.addEventListener("dblclick", function (event) {
        if (event.target.closest && event.target.closest("a")) { return; }
        event.preventDefault();
        autoFit(index);
      });
      /* startResize：处理对应交互。 */
      function startResize(event) {
        event.preventDefault();
        event.stopPropagation();
        var startX = event.clientX;
        var startWidth = widthOf(cols[index], defaults[index]);
        /* move：处理对应交互。 */
        function move(e) {
          var next = Math.max(60, startWidth + (e.clientX - startX));
          cols[index].style.width = next + "px";
        }
        /* up：处理对应交互。 */
        function up() {
          document.removeEventListener("mousemove", move);
          document.removeEventListener("mouseup", up);
          document.body.classList.remove("col-resizing");
          saveWidths();
        }
        document.body.classList.add("col-resizing");
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
      }
      handle.addEventListener("mousedown", startResize);
      th.addEventListener("mousedown", function (event) {
        if (event.button !== 0 || event.target.closest(".col-resizer")) { return; }
        var startX = event.clientX;
        var startWidth = widthOf(cols[index], defaults[index]);
        var moved = false;
        /* move：处理对应交互。 */
        function move(e) {
          if (!moved && Math.abs(e.clientX - startX) < 4) { return; }
          if (!moved) {
            moved = true;
            document.body.classList.add("col-resizing");
            e.preventDefault();
          }
          cols[index].style.width = Math.max(60, startWidth + (e.clientX - startX)) + "px";
        }
        /* up：处理对应交互。 */
        function up() {
          document.removeEventListener("mousemove", move);
          document.removeEventListener("mouseup", up);
          document.body.classList.remove("col-resizing");
          if (moved) {
            saveWidths();
            var swallow = function (clickEvent) {
              clickEvent.preventDefault();
              clickEvent.stopPropagation();
              document.removeEventListener("click", swallow, true);
            };
            document.addEventListener("click", swallow, true);
            window.setTimeout(function () {
              document.removeEventListener("click", swallow, true);
            }, 80);
          }
        }
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
      });
      handle.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
      });
    });
    table._autoFitAll = function () {
      headers.forEach(function (_th, index) { autoFit(index); });
      saveWidths();
    };
    table._resetCols = function () {
      try { window.localStorage.removeItem("colwidth:" + key); } catch (err) {}
      cols.forEach(function (col, i) { col.style.width = defaults[i] + "px"; });
    };
  }

  /* initSelectAll：处理对应交互。 */
  function initSelectAll() {
    var table = document.getElementById("linkTable");
    if (!table) { return; }
    var master = document.getElementById("selectAllPage");
    var boxes = function () {
      return Array.prototype.slice.call(table.querySelectorAll("tbody .row-select"));
    };
    var buttons = document.querySelectorAll("[data-requires-selection]");
    /* syncButtons：处理对应交互。 */
    function syncButtons() {
      var checked = boxes().some(function (box) { return box.checked; });
      buttons.forEach(function (button) { button.disabled = !checked; });
      if (master) {
        master.checked = boxes().length > 0 && boxes().every(function (box) { return box.checked; });
        master.indeterminate = !master.checked && checked;
      }
    }
    if (master) {
      master.checked = false;
      master.addEventListener("change", function () {
        boxes().forEach(function (box) { box.checked = master.checked; });
        syncButtons();
      });
    }
    boxes().forEach(function (box) {
      box.checked = false;
      box.addEventListener("change", syncButtons);
    });
    syncButtons();
    window.addEventListener("pageshow", function () {
      if (master) { master.checked = false; master.indeterminate = false; }
      boxes().forEach(function (box) { box.checked = false; });
      syncButtons();
    });
  }

  /* initResetButtons：处理对应交互。 */
  function initResetButtons() {
    document.querySelectorAll("[data-reset-table]").forEach(function (button) {
      button.addEventListener("click", function () {
        var table = document.getElementById(button.getAttribute("data-reset-table"));
        if (table && table._resetCols) { table._resetCols(); }
      });
    });
    document.querySelectorAll("[data-auto-table]").forEach(function (button) {
      button.addEventListener("click", function () {
        var table = document.getElementById(button.getAttribute("data-auto-table"));
        if (table && table._autoFitAll) { table._autoFitAll(); }
      });
    });
  }

  /* init：处理对应交互。 */
  function init() {
    document.querySelectorAll("table[data-resizable]").forEach(initResizable);
    initSelectAll();
    initResetButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
