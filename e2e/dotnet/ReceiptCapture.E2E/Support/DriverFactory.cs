using OpenQA.Selenium;
using OpenQA.Selenium.Chrome;
using OpenQA.Selenium.Remote;

namespace ReceiptCapture.E2E.Support;

public static class DriverFactory
{
    public static IWebDriver Create()
    {
        var options = new ChromeOptions();
        options.AddArguments("--window-size=1440,1000", "--disable-dev-shm-usage");
        if (TestSettings.Headless) options.AddArgument("--headless=new");
        // Keep the browser console, saved on failure (realtime and JS errors only show up there)
        options.SetLoggingPreference(LogType.Browser, LogLevel.All);

        IWebDriver driver = TestSettings.RemoteUrl is { } remote
            ? new RemoteWebDriver(new Uri(remote), options)
            : new ChromeDriver(options);

        // Explicit waits only: an implicit wait would slow down every "element is absent" check
        driver.Manage().Timeouts().ImplicitWait = TimeSpan.Zero;
        driver.Manage().Timeouts().PageLoad = TimeSpan.FromSeconds(60);
        return driver;
    }
}
