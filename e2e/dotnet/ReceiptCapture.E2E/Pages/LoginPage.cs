using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Pages;

public class LoginPage(IWebDriver driver)
{
    private readonly WebDriverWait _wait = new(driver, TimeSpan.FromSeconds(30));

    public void Open()
    {
        driver.Navigate().GoToUrl($"{TestSettings.BaseUrl}/login");
        _wait.Until(d => d.FindElements(By.Id("login_email")).Count > 0);
    }

    public void Submit(string user, string password)
    {
        var email = driver.FindElement(By.Id("login_email"));
        var secret = driver.FindElement(By.Id("login_password"));
        email.Clear();
        email.SendKeys(user);
        secret.Clear();
        secret.SendKeys(password);
        driver.FindElement(By.CssSelector(".btn-login")).Click();
    }

    /// <summary>Logs in and waits for the desk.</summary>
    public void LoginAs(string user, string password)
    {
        Open();
        Submit(user, password);
        _wait.Message = $"Login as {user} did not reach the desk";
        _wait.Until(d => d.Url.Contains("/app"));
    }

    /// <summary>Frappe shows a failed login in the button itself.</summary>
    public string WaitForError()
    {
        _wait.Message = "No login error shown";
        return _wait.Until(d =>
        {
            var text = d.FindElement(By.CssSelector(".btn-login")).Text;
            return text.Contains("Invalid") ? text : null;
        })!;
    }
}
