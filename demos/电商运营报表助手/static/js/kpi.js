/* ── KPI 切换脚本 ── */
/* 作用：点击经营分析指标卡时只更新趋势图。 */
/*  KPI 卡只局部切换趋势图，不整页刷新、不影响推广/计划/异常。 */
/* 页面脚本：初始化当前页交互。 */
(function () {
  "use strict";
  /* initKpiTrend：处理对应交互。 */
  function initKpiTrend() {
    var cards = document.querySelectorAll(".kpi-compact[data-metric]");
    if (!cards.length) { return; }
    var data = window.TREND_OPTIONS || {};
    cards.forEach(function (card) {
      card.addEventListener("click", function (ev) {
        ev.preventDefault();
        var metric = card.getAttribute("data-metric");
        var payload = data[metric];
        if (!payload) { return; }
        var el = document.getElementById("chart_trend");
        if (!el || typeof echarts === "undefined") { return; }
        var chart = echarts.getInstanceByDom(el);
        if (!chart) { return; }
        chart.setOption(payload.option, true);
        var title = document.getElementById("trendTitle");
        if (title) {
          var range = document.body.getAttribute("data-range") || "";
          var compare = payload.compare_label ? "（上期 " + payload.compare_label + "）" : "";
          title.textContent = payload.label + "趋势（按日）｜" + range + compare;
        }
        cards.forEach(function (other) { other.classList.remove("active"); });
        card.classList.add("active");
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initKpiTrend);
  } else { initKpiTrend(); }
})();
