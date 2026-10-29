namespace ReceiptCapture.E2E.Support;

/// <summary>Everything the suite needs from the environment, with defaults matching docker-compose.yml.</summary>
public static class TestSettings
{
    public static string BaseUrl { get; } = Env("BASE_URL", "http://erp.localhost:8080").TrimEnd('/');
    public static string AdminUser { get; } = Env("ADMIN_USER", "Administrator");
    public static string AdminPassword { get; } = Env("ADMIN_PASSWORD", "admin");
    public static string UserPassword { get; } = Env("E2E_USER_PASSWORD", "e2e-user-pass");
    public const string Reviewer = "reviewer@example.com";
    public const string NoAccessUser = "no-access@example.com";

    public static bool Headless { get; } = Env("HEADLESS", "1") != "0";

    /// <summary>Remote Selenium Grid or chromedriver; local Chrome via Selenium Manager when unset.</summary>
    public static string? RemoteUrl { get; } = Environment.GetEnvironmentVariable("SELENIUM_REMOTE_URL");

    /// <summary>OCR and a CPU-only model can take a while on a cold start.</summary>
    public static TimeSpan ExtractionTimeout { get; } =
        TimeSpan.FromMilliseconds(int.Parse(Env("EXTRACTION_TIMEOUT_MS", "240000")));

    /// <summary>e2e/fixtures, shared with the JavaScript suite.</summary>
    public static string FixturesDir { get; } = FindFixtures();

    private static string Env(string name, string fallback) =>
        Environment.GetEnvironmentVariable(name) is { Length: > 0 } value ? value : fallback;

    private static string FindFixtures()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            var candidate = Path.Combine(dir.FullName, "fixtures");
            if (File.Exists(Path.Combine(candidate, "receipt.png"))) return candidate;
        }
        throw new DirectoryNotFoundException("Could not find e2e/fixtures above " + AppContext.BaseDirectory);
    }
}
