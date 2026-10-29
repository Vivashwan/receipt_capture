using NUnit.Framework.Interfaces;
using OpenQA.Selenium;
using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

/// <summary>One browser per fixture, optionally logged in; saves a screenshot and the page HTML when a test fails.</summary>
public abstract class UiTest
{
    protected IWebDriver Driver { get; private set; } = null!;

    /// <summary>User to log in as before the fixture's tests; null for none.</summary>
    protected virtual (string User, string Password)? LoginAs => null;

    [OneTimeSetUp]
    public void StartBrowser()
    {
        Driver = DriverFactory.Create();
        if (LoginAs is var (user, password)) new LoginPage(Driver).LoginAs(user, password);
    }

    [TearDown]
    public void CaptureFailure()
    {
        if (TestContext.CurrentContext.Result.Outcome.Status != TestStatus.Failed) return;

        var dir = Path.Combine(TestContext.CurrentContext.WorkDirectory, "artifacts");
        Directory.CreateDirectory(dir);
        var name = string.Concat(TestContext.CurrentContext.Test.FullName.Select(c => char.IsLetterOrDigit(c) ? c : '-'));
        var png = Path.Combine(dir, name + ".png");
        try
        {
            ((ITakesScreenshot)Driver).GetScreenshot().SaveAsFile(png);
            File.WriteAllText(Path.Combine(dir, name + ".html"), Driver.PageSource);
            var console = Driver.Manage().Logs.GetLog(LogType.Browser).Select(entry => $"{entry.Level} {entry.Message}");
            File.WriteAllLines(Path.Combine(dir, name + ".console.log"), console);
            TestContext.AddTestAttachment(png);
        }
        catch (WebDriverException error)
        {
            TestContext.Out.WriteLine($"Could not capture failure artifacts: {error.Message}");
        }
    }

    [OneTimeTearDown]
    public void StopBrowser()
    {
        Driver?.Quit();
        Driver?.Dispose();
    }
}
