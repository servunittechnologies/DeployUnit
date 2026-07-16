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
      // Keep the original Host (localhost:3000) and add X-Forwarded-* so the
      // backend derives redirect/callback URLs on the single dev origin —
      // matching how the production ingress presents one origin to the app.
      changeOrigin: false,
      xfwd: true,
    })
  );
};
