// Fail before publishing a production site wired to localhost or the wrong origin.
if (process.env.NETLIFY === "true" && process.env.CONTEXT === "production") {
  for (const name of ["API_BASE_URL", "FRONTEND_ORIGIN"]) {
    let url;
    try {
      url = new URL(process.env[name]);
    } catch {
      /* handled below */
    }
    if (
      !url ||
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash ||
      process.env[name].endsWith("/") ||
      ["localhost", "127.0.0.1"].includes(url.hostname)
    ) {
      console.error(
        `${name} must be a complete HTTPS origin without credentials, a path or trailing slash. Set it for builds and functions in Netlify.`,
      );
      process.exit(1);
    }
  }
  console.log("CareerOS production gateway configuration checked.");
}
