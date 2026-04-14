import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import { Fragment, h } from "vue";

const EMBEDDED_STYLE_ID = "openakita-embedded-docs-style";
const EMBEDDED_INIT_SCRIPT_ID = "openakita-embedded-docs-init";
const EMBEDDED_INIT_SCRIPT_TEXT = `
(() => {
  if (typeof window === "undefined") return;
  if (window.parent && window.parent !== window) {
    document.documentElement.classList.add("openakita-embedded-docs");
  }
})();
`;
const EMBEDDED_STYLE_TEXT = `
html.openakita-embedded-docs,
html.openakita-embedded-docs body {
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
}

html.openakita-embedded-docs {
  --vp-sidebar-width: 0px;
}

.openakita-embedded-docs .VPNavBarHamburger {
  display: flex !important;
}

.openakita-embedded-docs .VPNavBarMenu,
.openakita-embedded-docs .VPNavBarExtra,
.openakita-embedded-docs .VPLocalNav,
.openakita-embedded-docs .VPDoc .aside,
.openakita-embedded-docs .VPDocAside {
  display: none !important;
}

.openakita-embedded-docs .VPNavBarTitle.has-sidebar,
.openakita-embedded-docs .VPNavBar.has-sidebar .title {
  padding-left: 0 !important;
}

.openakita-embedded-docs .VPContent,
.openakita-embedded-docs .VPContent.has-sidebar {
  margin: 0 !important;
  padding: 0 !important;
}

.openakita-embedded-docs .VPDoc,
.openakita-embedded-docs .VPDoc.has-sidebar,
.openakita-embedded-docs .VPDoc.has-aside {
  width: 100%;
  padding: 24px 16px 64px;
}

.openakita-embedded-docs .VPDoc .container {
  display: block !important;
  margin: 0 auto;
  width: 100%;
  max-width: 100%;
}

.openakita-embedded-docs .VPDoc .content {
  margin: 0 auto;
  padding: 0 !important;
  width: 100%;
  min-width: 0 !important;
  max-width: 920px;
}

.openakita-embedded-docs .VPDoc .content-container,
.openakita-embedded-docs .VPDoc.has-aside .content-container {
  width: 100%;
  max-width: 920px !important;
}

.openakita-embedded-docs .vp-doc,
.openakita-embedded-docs .vp-doc div,
.openakita-embedded-docs .vp-doc main {
  min-width: 0;
}

.openakita-embedded-docs .vp-doc {
  overflow-wrap: anywhere;
}

.openakita-embedded-docs .vp-doc pre,
.openakita-embedded-docs .vp-doc div[class*="language-"],
.openakita-embedded-docs .vp-doc table {
  max-width: 100%;
}

.openakita-embedded-docs .vp-doc table {
  display: block;
  overflow-x: auto;
}

.openakita-embedded-docs .VPNavScreen {
  top: calc(var(--vp-nav-height) + var(--vp-layout-top-height, 0px) + 8px);
  right: 12px;
  bottom: 12px;
  left: auto;
  padding: 0;
  width: min(320px, calc(100vw - 24px));
  border: 1px solid var(--vp-c-gutter);
  border-radius: 16px;
  background-color: var(--vp-c-bg-elv);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.18);
}

.openakita-embedded-docs .VPNavScreen .container {
  margin: 0;
  padding: 18px 18px 28px;
  max-width: none;
}

.openakita-embedded-docs .VPNavScreen.fade-enter-from .container,
.openakita-embedded-docs .VPNavScreen.fade-leave-to .container {
  transform: translateX(16px);
}

@media (min-width: 960px) {
  .openakita-embedded-docs .VPDoc,
  .openakita-embedded-docs .VPDoc.has-sidebar,
  .openakita-embedded-docs .VPDoc.has-aside {
    padding: 32px 24px 80px;
  }
}
`;

const DocsBanner = {
  setup() {
    return () =>
      h(
        "div",
        {
          style:
            "background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e; text-align: center; padding: 8px 16px; font-size: 13px; line-height: 1.5; border-bottom: 1px solid #f59e0b40;",
        },
        "⚠️ 本文档由 AI 生成，尚未完全人工审核校对，内容仅供参考。请结合实际界面操作，如有出入以软件实际功能为准。",
      );
  },
};

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      "layout-top": () =>
        h(Fragment, null, [
          h("script", { id: EMBEDDED_INIT_SCRIPT_ID }, EMBEDDED_INIT_SCRIPT_TEXT),
          h("style", { id: EMBEDDED_STYLE_ID }, EMBEDDED_STYLE_TEXT),
          h(DocsBanner),
        ]),
    });
  },
  enhanceApp({ router }) {
    if (typeof window === "undefined") return;

    if (window.parent && window.parent !== window) {
      document.documentElement.classList.add("openakita-embedded-docs");
    }

    router.onBeforeRouteChange = (to: string) => {
      if (to.includes("/web/") || to.includes("/web#")) {
        const hashIdx = to.indexOf("#");
        const hash = hashIdx >= 0 ? to.slice(hashIdx) : "";
        if (hash) {
          if (window.parent && window.parent !== window) {
            window.parent.postMessage(
              { type: "openakita-navigate", hash },
              "*",
            );
          } else {
            window.location.hash = hash;
          }
        }
        return false;
      }
    };
  },
} satisfies Theme;
