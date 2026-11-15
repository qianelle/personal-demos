/* 页面脚本：初始化当前页交互。 */
/* ── 悬浮提示脚本 ── */
/* 作用：为页面说明图标绑定悬浮提示。 */
(function () {
  "use strict";
  /* initTips：处理对应交互。 */
  function initTips() {
    document.querySelectorAll(".info-tip").forEach(function (tip) {
      tip.addEventListener("click", function (ev) {
        ev.stopPropagation();
        document.querySelectorAll(".info-tip.open").forEach(function (other) {
          if (other !== tip) { other.classList.remove("open"); }
        });
        tip.classList.toggle("open");
      });
    });
    document.addEventListener("click", function () {
      document.querySelectorAll(".info-tip.open").forEach(function (tip) {
        tip.classList.remove("open");
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTips);
  } else {
    initTips();
  }
})();
