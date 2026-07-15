// Dev-only: mirror the production ingress by forwarding ALL /api traffic
// (including full-page navigations like the SSO consume redirect) to the
// local backend. CRA's simple "proxy" field skips text/html requests, which
// breaks cookie-setting redirect endpoints — this middleware does not.
const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: process.env.DEV_BACKEND_URL || "http://127.0.0.1:8001",
      changeOrigin: true,
    })
  );
};
