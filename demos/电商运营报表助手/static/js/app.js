/* ── 图表渲染脚本 ── */
/* 作用：初始化页面图表并在窗口尺寸变化时重新布局。 */
/* 电商运营报表助手 · 前端渲染脚本
   图表数据全部由 Python 计算后通过 window.CHART_DATA 传入，前端只做 setOption 渲染，
   不在浏览器中做任何聚合。 */

/* EcomApp：页面图表入口。 */
window.EcomApp = (function () {
  "use strict";

  var instances = [];
  var initialized = false;

  /* showFallback：处理对应交互。 */
  function showFallback(el, message) {
    el.innerHTML = '<div class="empty">' + message + "</div>";
  }

  /* initCharts：处理对应交互。 */
  function initCharts() {
    if (initialized) { return; }
    initialized = true;
    var data = window.CHART_DATA || {};
    var layout = window.CHART_LAYOUT || [];
    if (!layout.length) { return; }

    if (typeof echarts === "undefined") {
      layout.forEach(function (item) {
        var el = document.getElementById(item.id);
        if (el) {
          showFallback(el, "本地图表库 static/vendor/echarts.min.js 未加载，图表不可渲染；数据仍可通过导出 Excel 获取。");
        }
      });
      return;
    }

    layout.forEach(function (item) {
      var el = document.getElementById(item.id);
      if (!el) { return; }
      var option = data[item.id];
      if (!option) {
        showFallback(el, "图表数据为空");
        return;
      }
      try {
        var fullTitles = option._full_titles;
        if (fullTitles) {
          delete option._full_titles;
          option.tooltip = option.tooltip || {};
          option.tooltip.formatter = function (params) {
            var point = Array.isArray(params) ? params[0] : params;
            var label = point.name;
            var full = fullTitles[label] || "";
            var value = Number(point.value);
            var valueText = isNaN(value) ? String(point.value)
              : value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return "<b>" + label + "</b><br/>" +
              (full ? "完整标题：" + full + "<br/>" : "") +
              "销售额：" + valueText + " 元";
          };
        }
        var chart = echarts.init(el);
        chart.setOption(option, true);
        instances.push(chart);
      } catch (err) {
        showFallback(el, "图表渲染异常：" + err.message);
      }
    });

    window.addEventListener("resize", function () {
      instances.forEach(function (chart) {
        try { chart.resize(); } catch (err) { /* 忽略 resize 异常 */ }
      });
    });
  }

  /* init：处理对应交互。 */
  function init() {
    initCharts();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return { initCharts: initCharts };
})();
