// Everything the suite needs from the environment, with defaults matching docker-compose.yml
export const config = {
	baseUrl: (process.env.BASE_URL || "http://erp.localhost:8080").replace(/\/$/, ""),
	adminUser: process.env.ADMIN_USER || "Administrator",
	adminPassword: process.env.ADMIN_PASSWORD || "admin",
	userPassword: process.env.E2E_USER_PASSWORD || "e2e-user-pass",
	reviewer: "reviewer@example.com",
	noAccessUser: "no-access@example.com",
	headless: process.env.HEADLESS !== "0",
	// Remote Selenium Grid / chromedriver URL; local Chrome via Selenium Manager when unset
	remoteUrl: process.env.SELENIUM_REMOTE_URL,
	// OCR + a CPU-only model can take a while on a cold start
	extractionTimeoutMs: Number(process.env.EXTRACTION_TIMEOUT_MS || 240000),
	artifactsDir: process.env.ARTIFACTS_DIR || "artifacts",
};
